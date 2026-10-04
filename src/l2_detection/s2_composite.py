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
    vis = bands['visual']

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


def prepare_s2_event_and_control_composites(
    cache_dir: str = "data/interim/s2_cache",
    dilation_buffer_m: float = 60.0,
    pixel_size_m: float = 10.0,
    event_date: Optional[str] = None
) -> Dict[str, Any]:
    """
    Load cached pre, post, and control Sentinel-2 scenes, apply SCL cloud/shadow dilation,
    and build multi-temporal per-pixel clear-sky composites.
    """
    c_path = Path(cache_dir)
    if not c_path.exists() or len(list(c_path.glob("*.npz"))) == 0:
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

    import re
    from datetime import datetime

    def load_processed(prefix: str) -> Dict[str, Any]:
        files = sorted(list(c_path.glob(f"{prefix}_*.npz")))
        if not files:
            raise FileNotFoundError(f"Missing cached S2 scene for {prefix} in {cache_dir}")
        data = np.load(files[0])
        bands = {k: data[k] for k in data.files}
        proc = process_s2_features(bands, dilation_buffer_m=dilation_buffer_m, pixel_size_m=pixel_size_m)
        proc['filename'] = files[0].stem
        m_dt = re.search(r'(\d{4})(\d{2})(\d{2})T', files[0].stem)
        dt_str = f"{m_dt.group(1)}-{m_dt.group(2)}-{m_dt.group(3)}" if m_dt else ""
        proc['date'] = dt_str
        if event_date and dt_str:
            try:
                ev_dt = datetime.fromisoformat(event_date)
                sc_dt = datetime.fromisoformat(dt_str)
                proc['delta_days'] = abs((sc_dt - ev_dt).days)
            except Exception:
                proc['delta_days'] = 0
        else:
            proc['delta_days'] = 0
        return proc

    s_pre_119 = load_processed("pre_119")
    s_pre_076 = load_processed("pre_076")
    s_post_119 = load_processed("post_119")
    s_post_076 = load_processed("post_076")
    s_ctrl_119 = load_processed("ctrl_119")

    # Multi-temporal compositing (earliest clear pixel preferred for post composite)
    pre_composite = composite_scenes([s_pre_119, s_pre_076])
    post_scenes_sorted = sorted([s_post_119, s_post_076], key=lambda s: s.get('date', ''))
    post_composite = composite_scenes(post_scenes_sorted)
    ctrl_post_composite = composite_scenes([s_ctrl_119, s_pre_076])

    # Event differences
    s2_event_valid = pre_composite['is_clear'] & post_composite['is_clear']
    d_ndvi_event = post_composite['ndvi'] - pre_composite['ndvi']
    d_bsi_event = post_composite['bsi'] - pre_composite['bsi']

    # Control differences
    s2_ctrl_valid = pre_composite['is_clear'] & ctrl_post_composite['is_clear']
    d_ndvi_ctrl = ctrl_post_composite['ndvi'] - pre_composite['ndvi']
    d_bsi_ctrl = ctrl_post_composite['bsi'] - pre_composite['bsi']

    def _parse_scene_meta(fn: str, default_orbit: str) -> Dict[str, str]:
        m_dt = re.search(r'(\d{4})(\d{2})(\d{2})T', fn)
        dt = f"{m_dt.group(1)}-{m_dt.group(2)}-{m_dt.group(3)}" if m_dt else ""
        return {"scene_id": fn, "date": dt, "orbit": default_orbit}

    scenes_used = {
        "pre": [
            _parse_scene_meta(s_pre_119['filename'], "R119"),
            _parse_scene_meta(s_pre_076['filename'], "R076")
        ],
        "post": [
            _parse_scene_meta(s_post_119['filename'], "R119"),
            _parse_scene_meta(s_post_076['filename'], "R076")
        ],
        "control_post": [
            _parse_scene_meta(s_ctrl_119['filename'], "R119")
        ]
    }

    # In-channel change vector magnitude (B2, B3, B4, B8, B11, B12, post vs pre + dNDWI + dBSI)
    in_channel_change_event = compute_in_channel_change_vector(pre_composite, post_composite)
    in_channel_change_ctrl = compute_in_channel_change_vector(pre_composite, ctrl_post_composite)

    # Compute representative optical evidence string
    clear_d = post_composite['acq_date'][post_composite['is_clear']]
    clear_days = post_composite['delta_days'][post_composite['is_clear']]
    if len(clear_d) > 0:
        from collections import Counter
        rep_date, _ = Counter(clear_d).most_common(1)[0]
        rep_days, _ = Counter(clear_days).most_common(1)[0]
        optical_evidence_note = f"optical evidence from {rep_date} ({rep_days} days after event)"
    else:
        optical_evidence_note = ""

    return {
        "scenes_used": scenes_used,
        "pre_composite": pre_composite,
        "post_composite": post_composite,
        "ctrl_post_composite": ctrl_post_composite,
        "d_ndvi_event": d_ndvi_event,
        "d_bsi_event": d_bsi_event,
        "s2_event_valid": s2_event_valid,
        "d_ndvi_ctrl": d_ndvi_ctrl,
        "d_bsi_ctrl": d_bsi_ctrl,
        "s2_ctrl_valid": s2_ctrl_valid,
        "in_channel_change_event": in_channel_change_event,
        "in_channel_change_ctrl": in_channel_change_ctrl,
        "optical_evidence_note": optical_evidence_note
    }

