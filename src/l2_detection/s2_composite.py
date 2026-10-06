"""
Sentinel-2 Optical Compositing & Feature Engineering Module for Layer 2.
Selects best clear pixels across multi-temporal S2 scenes and derives spectral indices:
- NDVI, BSI, and NDWI.
- SCL cloud and shadow masking with configurable dilation buffer (default 60 m).
"""

import os
import glob
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
import numpy as np
import rasterio
from rasterio.windows import from_bounds
from scipy.ndimage import distance_transform_edt
import logging

logger = logging.getLogger("s2_composite")


def load_or_cache_s2_scene(
    item_id: str,
    assets: Dict[str, Any],
    bounds: Tuple[float, float, float, float],
    target_shape: Tuple[int, int],
    s2_token: str = "",
    cache_dir: str = "data/interim/s2_cache"
) -> Dict[str, np.ndarray]:
    """Load S2 bands for a scene from local cache or remote STAC URL."""
    c_path = Path(cache_dir)
    c_path.mkdir(parents=True, exist_ok=True)
    cache_file = c_path / f"{item_id[:35]}.npz"

    if cache_file.exists():
        d = np.load(cache_file)
        return {k: d[k] for k in d.files}

    import requests
    http = requests.Session()
    http.trust_env = False

    env = rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN='EMPTY_DIR', CPL_VSIL_CURL_USE_HEAD='NO', GDAL_HTTP_CONNECTTIMEOUT='30')
    bands = {}
    with env:
        for b_name in ['B02', 'B03', 'B04', 'B08', 'B11', 'SCL', 'visual']:
            url = assets[b_name]['href']
            if s2_token and "?" not in url:
                url = f"{url}?{s2_token}"
            with rasterio.open(url) as s:
                w = from_bounds(bounds[0], bounds[1], bounds[2], bounds[3], transform=s.transform)
                if b_name == 'visual':
                    arr = s.read(window=w, out_shape=(3, *target_shape))
                else:
                    arr = s.read(1, window=w, out_shape=target_shape)
                bands[b_name] = arr

    np.savez_compressed(cache_file, **bands)
    return bands


def process_s2_features(
    bands: Dict[str, np.ndarray],
    dilation_buffer_m: float = 60.0,
    pixel_size_m: float = 10.0
) -> Dict[str, np.ndarray]:
    """
    Process raw S2 bands into indices and dilated cloud/shadow mask:
    - Dilates cloud/shadow mask by dilation_buffer_m (default 60 m) to prevent edge artifacts.
    - Computes NDVI, BSI, and NDWI.
    """
    b02 = bands['B02'].astype(np.float32)
    b03 = bands['B03'].astype(np.float32)
    b04 = bands['B04'].astype(np.float32)
    b08 = bands['B08'].astype(np.float32)
    b11 = bands['B11'].astype(np.float32)
    b12 = bands.get('B12', bands.get('b12', b11)).astype(np.float32)
    scl = bands['SCL']
    if 'visual' in bands:
        vis = bands['visual']
    else:
        vis = np.clip(np.stack([b04, b03, b02], axis=0) / 3000.0 * 255.0, 0, 255).astype(np.uint8)

    # SCL invalid classes:
    # 0: NoData, 1: Saturated/Defective, 3: Cloud Shadows, 8: Cloud Medium Prob,
    # 9: Cloud High Prob, 10: Thin Cirrus, 11: Snow
    raw_cloud = np.isin(scl, [0, 1, 3, 8, 9, 10, 11]) | (b04 <= 0) | (b08 <= 0) | (b02 <= 0) | (b11 <= 0) | (b12 <= 0)

    # Dilate cloud mask by buffer (removes false edge artifacts)
    radius_pixels = max(1.0, dilation_buffer_m / pixel_size_m)
    dilated_cloud = distance_transform_edt(~raw_cloud) <= radius_pixels
    is_clear = ~dilated_cloud

    ndvi = (b08 - b04) / np.maximum(b08 + b04, 1e-4)
    bsi = ((b11 + b04) - (b08 + b02)) / np.maximum((b11 + b04) + (b08 + b02), 1e-4)
    ndwi = (b03 - b08) / np.maximum(b03 + b08, 1e-4)

    return {
        'is_clear': is_clear,
        'dilated_cloud': dilated_cloud,
        'ndvi': ndvi,
        'bsi': bsi,
        'ndwi': ndwi,
        'b02': b02,
        'b03': b03,
        'b04': b04,
        'b08': b08,
        'b11': b11,
        'b12': b12,
        'vis': vis
    }


def composite_scenes(
    scenes: List[Dict[str, np.ndarray]]
) -> Dict[str, Any]:
    """
    Per-pixel best clear value compositing across a sequence of scenes.
    Prefers the earliest clear scene in the list; if none is clear, marked as cloudy.
    Tracks per-pixel acquisition date and days after event.
    """
    if not scenes:
        raise ValueError("No scenes provided for compositing")

    h, w = scenes[0]['ndvi'].shape
    composite_clear = np.zeros((h, w), dtype=bool)
    composite_ndvi = np.zeros((h, w), dtype=np.float32)
    composite_bsi = np.zeros((h, w), dtype=np.float32)
    composite_ndwi = np.zeros((h, w), dtype=np.float32)
    composite_b02 = np.zeros((h, w), dtype=np.float32)
    composite_b03 = np.zeros((h, w), dtype=np.float32)
    composite_b04 = np.zeros((h, w), dtype=np.float32)
    composite_b08 = np.zeros((h, w), dtype=np.float32)
    composite_b11 = np.zeros((h, w), dtype=np.float32)
    composite_b12 = np.zeros((h, w), dtype=np.float32)
    composite_vis = np.zeros((3, h, w), dtype=np.uint8)
    composite_date = np.full((h, w), "", dtype=object)
    composite_days = np.full((h, w), -1, dtype=int)

    filled = np.zeros((h, w), dtype=bool)

    for sc in scenes:
        clear = sc['is_clear']
        to_fill = clear & (~filled)
        if np.any(to_fill):
            composite_ndvi[to_fill] = sc['ndvi'][to_fill]
            composite_bsi[to_fill] = sc['bsi'][to_fill]
            composite_ndwi[to_fill] = sc['ndwi'][to_fill]
            composite_b02[to_fill] = sc['b02'][to_fill]
            composite_b03[to_fill] = sc['b03'][to_fill]
            composite_b04[to_fill] = sc['b04'][to_fill]
            composite_b08[to_fill] = sc['b08'][to_fill]
            composite_b11[to_fill] = sc['b11'][to_fill]
            composite_b12[to_fill] = sc['b12'][to_fill]
            composite_vis[:, to_fill] = sc['vis'][:, to_fill]
            composite_date[to_fill] = sc.get('date', '')
            composite_days[to_fill] = sc.get('delta_days', 0)
            filled[to_fill] = True
            composite_clear[to_fill] = True

    # For remaining pixels where no scene is clear, fill with first scene values (masked as invalid)
    unfilled = ~filled
    if np.any(unfilled):
        composite_ndvi[unfilled] = scenes[0]['ndvi'][unfilled]
        composite_bsi[unfilled] = scenes[0]['bsi'][unfilled]
        composite_ndwi[unfilled] = scenes[0]['ndwi'][unfilled]
        composite_b02[unfilled] = scenes[0]['b02'][unfilled]
        composite_b03[unfilled] = scenes[0]['b03'][unfilled]
        composite_b04[unfilled] = scenes[0]['b04'][unfilled]
        composite_b08[unfilled] = scenes[0]['b08'][unfilled]
        composite_b11[unfilled] = scenes[0]['b11'][unfilled]
        composite_b12[unfilled] = scenes[0]['b12'][unfilled]
        composite_vis[:, unfilled] = scenes[0]['vis'][:, unfilled]
        composite_date[unfilled] = scenes[0].get('date', '')
        composite_days[unfilled] = scenes[0].get('delta_days', 0)

    return {
        'is_clear': composite_clear,
        'ndvi': composite_ndvi,
        'bsi': composite_bsi,
        'ndwi': composite_ndwi,
        'b02': composite_b02,
        'b03': composite_b03,
        'b04': composite_b04,
        'b08': composite_b08,
        'b11': composite_b11,
        'b12': composite_b12,
        'vis': composite_vis,
        'acq_date': composite_date,
        'delta_days': composite_days
    }


def compute_in_channel_change_vector(
    pre_composite: Dict[str, np.ndarray],
    post_composite: Dict[str, np.ndarray]
) -> np.ndarray:
    """
    Computes change vector magnitude over S2 bands (B2, B3, B4, B8, B11, B12, post vs pre)
    plus Delta NDWI and Delta BSI.
    """
    band_keys = ['b02', 'b03', 'b04', 'b08', 'b11', 'b12']
    sq_bands = np.zeros_like(pre_composite['ndvi'], dtype=np.float32)
    for b in band_keys:
        diff = (post_composite[b] - pre_composite[b]) / 10000.0
        sq_bands += diff ** 2

    d_ndwi = post_composite['ndwi'] - pre_composite['ndwi']
    d_bsi = post_composite['bsi'] - pre_composite['bsi']

    cvm = np.sqrt(sq_bands + (d_ndwi ** 2) + (d_bsi ** 2)).astype(np.float32)
    return cvm


_TERRAIN_SHADOW_CACHE: Dict[Tuple, np.ndarray] = {}


def compute_terrain_cast_shadow(
    dem: np.ndarray,
    sun_elevation_deg: float,
    sun_azimuth_deg: float,
    pixel_size_m: float = 10.0,
    max_dist_m: float = 3000.0
) -> np.ndarray:
    """
    Computes terrain cast shadow mask from DEM and sun vector using line-of-sight ray tracing.
    Returns boolean mask where True indicates pixel is in terrain cast shadow.
    """
    cache_key = (
        round(float(sun_elevation_deg), 1),
        round(float(sun_azimuth_deg), 1),
        round(float(pixel_size_m), 1),
        dem.shape,
        float(dem.flat[0]),
        float(dem.flat[-1])
    )
    if cache_key in _TERRAIN_SHADOW_CACHE:
        return _TERRAIN_SHADOW_CACHE[cache_key].copy()

    elev_rad = np.radians(sun_elevation_deg)
    az_rad = np.radians(sun_azimuth_deg)
    tan_elev = np.tan(elev_rad)
    dr = -np.cos(az_rad)
    dc = np.sin(az_rad)
    step_norm = np.sqrt(dr**2 + dc**2)
    dr /= step_norm
    dc /= step_norm
    max_steps = int(max_dist_m / pixel_size_m)
    h, w = dem.shape
    cast_shadow = np.zeros((h, w), dtype=bool)

    from scipy.ndimage import shift
    for s in range(1, min(max_steps, 150) + 1):
        delta_r = s * dr
        delta_c = s * dc
        dist_m = s * pixel_size_m
        height_diff_needed = dist_m * tan_elev
        shifted_dem = shift(dem, (-delta_r, -delta_c), order=1, mode='nearest')
        is_blocked = (shifted_dem - dem) > height_diff_needed
        cast_shadow |= is_blocked

    _TERRAIN_SHADOW_CACHE[cache_key] = cast_shadow
    return cast_shadow


def prepare_s2_event_and_control_composites(
    cache_dir: str = "data/interim/s2_cache",
    dilation_buffer_m: float = 60.0,
    pixel_size_m: float = 10.0,
    event_date: Optional[str] = None,
    dem_path: Optional[str] = None,
    interim_dir: Optional[str] = None
) -> Dict[str, Any]:
    """
    Load cached pre, post, and control Sentinel-2 scenes dynamically.
    Enforces the same-geometry rule: comparisons (event and control) are strictly evaluated
    within matching relative orbits per pixel. Masks terrain cast shadow and snow/ice.
    """
    import re
    from datetime import datetime
    from collections import Counter

    c_path = Path(cache_dir)
    npz_files = sorted([f for f in c_path.glob("*.npz") if not f.name.startswith(".") and "tmp" not in f.name])
    if not c_path.exists() or len(npz_files) == 0:
        logger.warning("[WARNING] Missing input: Clear Sentinel-2 optical scenes unavailable in cache. Falling back to Sentinel-1 SAR.")
        return {
            "scenes_used": {"pre": [], "post": [], "control_post": []},
            "pre_composite": None,
            "post_composite": None,
            "ctrl_post_composite": None,
            "d_ndvi_event": None,
            "d_bsi_event": None,
            "s2_event_valid": False,
            "d_ndvi_ctrl": None,
            "d_bsi_ctrl": None,
            "s2_ctrl_valid": False,
            "in_channel_change_event": None,
            "in_channel_change_ctrl": None,
            "optical_evidence_note": ""
        }

    # Load and resample DEM if available for terrain cast shadow computation
    dem_array = None
    dem_candidates = []
    if dem_path and Path(dem_path).exists():
        dem_candidates.append(Path(dem_path))
    if interim_dir:
        int_p = Path(interim_dir)
        dem_candidates.extend([
            int_p / "dem.tif",
            int_p.parent / "raw" / "dem" / "dem.tif",
            int_p.parent / "raw" / "dem" / "dem_buffered.tif",
            int_p.parent / "raw" / "dem_buffered" / "dem_buffered.tif"
        ])
    dem_candidates.extend([
        c_path.parent / "dem.tif",
        c_path.parent.parent / "raw" / "dem" / "dem.tif",
        c_path.parent.parent / "raw" / "dem" / "dem_buffered.tif",
        Path("data/raw/dem/dem.tif"),
        Path("data/raw/dem/dem_buffered.tif")
    ])

    dem_file = None
    for cand in dem_candidates:
        if cand.exists():
            dem_file = cand
            break

    ref_tif = None
    if interim_dir and (Path(interim_dir) / "hand.tif").exists():
        ref_tif = Path(interim_dir) / "hand.tif"
    elif (c_path.parent / "hand.tif").exists():
        ref_tif = c_path.parent / "hand.tif"

    if dem_file is not None and ref_tif is not None:
        try:
            from src.l1_preprocessing.grid import resample_dem_to_grid
            with rasterio.open(ref_tif) as rf:
                ref_profile = rf.profile
            dem_array = resample_dem_to_grid(str(dem_file), ref_profile)
        except Exception as e:
            logger.warning(f"Could not resample DEM for terrain shadow: {e}")
            dem_array = None

    # Load and process each scene
    scenes_by_orbit: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
    scenes_meta = {"pre": [], "post": [], "control_post": []}

    for f in npz_files:
        if "seasonal_pre" in f.stem or "seas_pre" in f.stem:
            role = "seasonal_pre"
        elif "seasonal_post" in f.stem or "seas_post" in f.stem:
            role = "seasonal_post"
        else:
            m_role = re.match(r'^(pre|post|ctrl)', f.stem)
            role = m_role.group(1) if m_role else "post"

        m_orb = re.search(r'R(\d{3})', f.stem) or re.search(r'(?:pre|post|ctrl|seasonal)_(\d{3})', f.stem)
        orbit = f"R{m_orb.group(1)}" if m_orb else "UNKNOWN"
        m_dt = re.search(r'(\d{4})(\d{2})(\d{2})T', f.stem)
        dt_str = f"{m_dt.group(1)}-{m_dt.group(2)}-{m_dt.group(3)}" if m_dt else ""

        data = np.load(f)
        bands = {k: data[k] for k in data.files}
        proc = process_s2_features(bands, dilation_buffer_m=dilation_buffer_m, pixel_size_m=pixel_size_m)
        proc['filename'] = f.stem
        proc['date'] = dt_str
        proc['orbit'] = orbit
        proc['role'] = role

        sun_elev = float(data['sun_elevation']) if 'sun_elevation' in data else 65.0
        sun_az = float(data['sun_azimuth']) if 'sun_azimuth' in data else 135.0

        # Terrain cast shadow mask & snow mask
        if dem_array is not None:
            shad = compute_terrain_cast_shadow(dem_array, sun_elev, sun_az, pixel_size_m=pixel_size_m)
            if shad.shape != proc['is_clear'].shape:
                min_h = min(shad.shape[0], proc['is_clear'].shape[0])
                min_w = min(shad.shape[1], proc['is_clear'].shape[1])
                shad_sub = np.zeros_like(proc['is_clear'])
                shad_sub[:min_h, :min_w] = shad[:min_h, :min_w]
                proc['is_clear'] &= (~shad_sub)
            else:
                proc['is_clear'] &= (~shad)

        # SCL == 11 is Snow/Ice
        scl = bands.get('SCL')
        if scl is not None:
            proc['is_clear'] &= (scl != 11)

        if event_date and dt_str:
            try:
                ev_dt = datetime.fromisoformat(event_date)
                sc_dt = datetime.fromisoformat(dt_str)
                proc['delta_days'] = abs((sc_dt - ev_dt).days)
            except Exception:
                proc['delta_days'] = 0
        else:
            proc['delta_days'] = 0

        if orbit not in scenes_by_orbit:
            scenes_by_orbit[orbit] = {"pre": [], "post": [], "ctrl": [], "seasonal_pre": [], "seasonal_post": []}
        scenes_by_orbit[orbit][role].append(proc)

        meta_key = "control_post" if role in ("ctrl", "seasonal_post") else role
        scenes_meta.setdefault(meta_key, []).append({"scene_id": f.stem, "date": dt_str, "orbit": orbit})

    # For each orbit, build intra-orbit composites and differences (SAME-GEOMETRY RULE)
    orbit_diffs = {}
    for orb, sc_dict in scenes_by_orbit.items():
        pre_list = sc_dict["pre"]
        post_list = sc_dict["post"]
        ctrl_list = sc_dict["ctrl"]

        if not pre_list or not post_list:
            continue

        pre_comp = composite_scenes(sorted(pre_list, key=lambda s: s.get('date', ''), reverse=True))
        post_comp = composite_scenes(sorted(post_list, key=lambda s: s.get('date', '')))

        # Intra-orbit event difference
        valid_ev = pre_comp['is_clear'] & post_comp['is_clear']
        d_ndvi_ev = post_comp['ndvi'] - pre_comp['ndvi']
        d_bsi_ev = post_comp['bsi'] - pre_comp['bsi']
        cvm_ev = compute_in_channel_change_vector(pre_comp, post_comp)

        # Intra-orbit control difference
        if ctrl_list:
            ctrl_comp = composite_scenes(ctrl_list)
            valid_ctrl = pre_comp['is_clear'] & ctrl_comp['is_clear']
            d_ndvi_ctrl = ctrl_comp['ndvi'] - pre_comp['ndvi']
            d_bsi_ctrl = ctrl_comp['bsi'] - pre_comp['bsi']
            cvm_ctrl = compute_in_channel_change_vector(pre_comp, ctrl_comp)
        else:
            ctrl_comp = None
            valid_ctrl = np.zeros_like(valid_ev, dtype=bool)
            d_ndvi_ctrl = np.zeros_like(d_ndvi_ev, dtype=np.float32)
            d_bsi_ctrl = np.zeros_like(d_bsi_ev, dtype=np.float32)
            cvm_ctrl = np.zeros_like(cvm_ev, dtype=np.float32)

        # Intra-orbit seasonal control difference
        s_pre_list = sc_dict.get("seasonal_pre", [])
        s_post_list = sc_dict.get("seasonal_post", [])
        if s_pre_list and s_post_list:
            s_pre_comp = composite_scenes(s_pre_list)
            s_post_comp = composite_scenes(sorted(s_post_list, key=lambda s: s.get('date', '')))
            valid_seas = s_pre_comp['is_clear'] & s_post_comp['is_clear']
            d_ndvi_seas = s_post_comp['ndvi'] - s_pre_comp['ndvi']
            d_bsi_seas = s_post_comp['bsi'] - s_pre_comp['bsi']
        else:
            valid_seas = np.zeros_like(valid_ev, dtype=bool)
            d_ndvi_seas = np.zeros_like(d_ndvi_ev, dtype=np.float32)
            d_bsi_seas = np.zeros_like(d_bsi_ev, dtype=np.float32)

        orbit_diffs[orb] = {
            "pre_comp": pre_comp,
            "post_comp": post_comp,
            "ctrl_comp": ctrl_comp,
            "valid_ev": valid_ev,
            "d_ndvi_ev": d_ndvi_ev,
            "d_bsi_ev": d_bsi_ev,
            "cvm_ev": cvm_ev,
            "valid_ctrl": valid_ctrl,
            "d_ndvi_ctrl": d_ndvi_ctrl,
            "d_bsi_ctrl": d_bsi_ctrl,
            "cvm_ctrl": cvm_ctrl,
            "valid_seas": valid_seas,
            "d_ndvi_seas": d_ndvi_seas,
            "d_bsi_seas": d_bsi_seas,
            "delta_days": post_comp['delta_days']
        }

    if not orbit_diffs:
        logger.warning("[WARNING] No complete same-orbit S2 pre/post pair found.")
        return {
            "scenes_used": scenes_meta,
            "pre_composite": None,
            "post_composite": None,
            "ctrl_post_composite": None,
            "d_ndvi_event": None,
            "d_bsi_event": None,
            "s2_event_valid": False,
            "d_ndvi_ctrl": None,
            "d_bsi_ctrl": None,
            "s2_ctrl_valid": False,
            "in_channel_change_event": None,
            "in_channel_change_ctrl": None,
            "optical_evidence_note": ""
        }

    first_orb = next(iter(orbit_diffs.values()))
    h, w = first_orb['valid_ev'].shape
    spectral_keys = ['ndvi', 'bsi', 'ndwi', 'b02', 'b03', 'b04', 'b08', 'b11', 'b12']
    final_post_comp = {k: np.zeros((h, w), dtype=np.float32) for k in spectral_keys}
    final_pre_comp = {k: np.zeros((h, w), dtype=np.float32) for k in spectral_keys}
    final_ctrl_comp = {k: np.zeros((h, w), dtype=np.float32) for k in spectral_keys}

    final_post_vis = np.zeros((3, h, w), dtype=np.uint8)
    final_pre_vis = np.zeros((3, h, w), dtype=np.uint8)
    final_acq_date = np.full((h, w), "", dtype=object)
    final_delta_days = np.full((h, w), 999, dtype=int)

    final_valid_ev = np.zeros((h, w), dtype=bool)
    final_d_ndvi_ev = np.zeros((h, w), dtype=np.float32)
    final_d_bsi_ev = np.zeros((h, w), dtype=np.float32)
    final_cvm_ev = np.zeros((h, w), dtype=np.float32)

    final_valid_ctrl = np.zeros((h, w), dtype=bool)
    final_d_ndvi_ctrl = np.zeros((h, w), dtype=np.float32)
    final_d_bsi_ctrl = np.zeros((h, w), dtype=np.float32)
    final_cvm_ctrl = np.zeros((h, w), dtype=np.float32)

    final_valid_seas = np.zeros((h, w), dtype=bool)
    final_d_ndvi_seas = np.zeros((h, w), dtype=np.float32)
    final_d_bsi_seas = np.zeros((h, w), dtype=np.float32)

    sorted_orbs = sorted(
        orbit_diffs.keys(),
        key=lambda o: np.min(orbit_diffs[o]['delta_days'][orbit_diffs[o]['valid_ev']]) if np.any(orbit_diffs[o]['valid_ev']) else 999
    )

    for orb in sorted_orbs:
        od = orbit_diffs[orb]
        fill_mask = od['valid_ev'] & (~final_valid_ev | (od['delta_days'] < final_delta_days))
        if np.any(fill_mask):
            final_valid_ev[fill_mask] = True
            final_d_ndvi_ev[fill_mask] = od['d_ndvi_ev'][fill_mask]
            final_d_bsi_ev[fill_mask] = od['d_bsi_ev'][fill_mask]
            final_cvm_ev[fill_mask] = od['cvm_ev'][fill_mask]
            final_post_vis[:, fill_mask] = od['post_comp']['vis'][:, fill_mask]
            final_pre_vis[:, fill_mask] = od['pre_comp']['vis'][:, fill_mask]
            final_acq_date[fill_mask] = od['post_comp']['acq_date'][fill_mask]
            final_delta_days[fill_mask] = od['delta_days'][fill_mask]
            for k in spectral_keys:
                final_post_comp[k][fill_mask] = od['post_comp'][k][fill_mask]
                final_pre_comp[k][fill_mask] = od['pre_comp'][k][fill_mask]

        ctrl_fill = od['valid_ctrl'] & (~final_valid_ctrl)
        if np.any(ctrl_fill):
            final_valid_ctrl[ctrl_fill] = True
            final_d_ndvi_ctrl[ctrl_fill] = od['d_ndvi_ctrl'][ctrl_fill]
            final_d_bsi_ctrl[ctrl_fill] = od['d_bsi_ctrl'][ctrl_fill]
            final_cvm_ctrl[ctrl_fill] = od['cvm_ctrl'][ctrl_fill]
            if od['ctrl_comp'] is not None:
                for k in spectral_keys:
                    if k in od['ctrl_comp']:
                        final_ctrl_comp[k][ctrl_fill] = od['ctrl_comp'][k][ctrl_fill]

        seas_fill = od['valid_seas'] & (~final_valid_seas)
        if np.any(seas_fill):
            final_valid_seas[seas_fill] = True
            final_d_ndvi_seas[seas_fill] = od['d_ndvi_seas'][seas_fill]
            final_d_bsi_seas[seas_fill] = od['d_bsi_seas'][seas_fill]

    # For unfilled pixels, fill background visual from first orbit
    unfilled = ~final_valid_ev
    if np.any(unfilled):
        first_post = first_orb['post_comp']
        first_pre = first_orb['pre_comp']
        final_post_vis[:, unfilled] = first_post['vis'][:, unfilled]
        final_pre_vis[:, unfilled] = first_pre['vis'][:, unfilled]
        final_acq_date[unfilled] = first_post['acq_date'][unfilled]
        for k in spectral_keys:
            final_post_comp[k][unfilled] = first_post[k][unfilled]
            final_pre_comp[k][unfilled] = first_pre[k][unfilled]

    final_post_comp['vis'] = final_post_vis
    final_post_comp['is_clear'] = final_valid_ev
    final_post_comp['acq_date'] = final_acq_date
    final_post_comp['delta_days'] = final_delta_days

    final_pre_comp['vis'] = final_pre_vis
    final_pre_comp['is_clear'] = final_valid_ev

    final_ctrl_comp['is_clear'] = final_valid_ctrl

    # Optical evidence note
    clear_dates = final_acq_date[final_valid_ev]
    clear_days = final_delta_days[final_valid_ev]
    if len(clear_dates) > 0:
        rep_date, _ = Counter(clear_dates).most_common(1)[0]
        rep_days, _ = Counter(clear_days).most_common(1)[0]
        optical_evidence_note = f"optical evidence from {rep_date} ({rep_days} days after event)"
    else:
        optical_evidence_note = ""

    return {
        "scenes_used": scenes_meta,
        "pre_composite": final_pre_comp,
        "post_composite": final_post_comp,
        "ctrl_post_composite": final_ctrl_comp,
        "d_ndvi_event": final_d_ndvi_ev,
        "d_bsi_event": final_d_bsi_ev,
        "s2_event_valid": final_valid_ev,
        "d_ndvi_ctrl": final_d_ndvi_ctrl,
        "d_bsi_ctrl": final_d_bsi_ctrl,
        "s2_ctrl_valid": final_valid_ctrl,
        "d_ndvi_seasonal": final_d_ndvi_seas if np.any(final_valid_seas) else None,
        "d_bsi_seasonal": final_d_bsi_seas if np.any(final_valid_seas) else None,
        "s2_seasonal_valid": final_valid_seas if np.any(final_valid_seas) else None,
        "in_channel_change_event": final_cvm_ev,
        "in_channel_change_ctrl": final_cvm_ctrl,
        "optical_evidence_note": optical_evidence_note
    }

