"""
Layer 2 Detection Orchestrator.
Primary Sensor: Sentinel-2 Optical Multi-temporal Composites (ΔNDVI, ΔBSI, NDWI)
Fallback Sensor: Sentinel-1 SAR (Ascending Pre-stack Z-score + Descending Orbit 19 Log-ratio)
Cloud/Shadow Masking: SCL dilated by 60 m buffer to eliminate cloud boundary artifacts.
Control Thresholding: 1st percentile of control pair in active HAND corridor.
Hazard Classes:
  1: Permanent Water (Pre NDWI + OSM waterways)
  2: Flood / Debris Affected (Vegetation loss & bare sediment deposition)
"""

import os
import gc
import json
import logging
import argparse
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List
import numpy as np
import rasterio
from rasterio.features import rasterize
import geopandas as gpd
from scipy.ndimage import distance_transform_edt, label
import yaml

from .thresholds import (
    compute_s2_control_thresholds,
    compute_s1_zscore_control_threshold,
    compute_in_channel_control_threshold,
    compute_builtup_control_threshold,
    smooth_log_ratio_mean
)
from .s2_composite import prepare_s2_event_and_control_composites
from .water import detect_permanent_water
from .hydraulic_fill import compute_inferred_flood_corridor
from .vectorizer import vectorize_hazard_classes
from .quicklook import render_layer2_quicklook

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("layer2_detection")


def save_single_band_geotiff(
    out_path: str,
    array: np.ndarray,
    ref_profile: Dict[str, Any],
    dtype: str = "uint8",
    nodata: Optional[int] = 0
) -> str:
    """Save 2D array as compressed single-band GeoTIFF."""
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    prof = ref_profile.copy()
    for k in ["blockxsize", "blockysize", "tiled"]:
        prof.pop(k, None)
    prof.update({
        "driver": "GTiff",
        "count": 1,
        "dtype": dtype,
        "compress": "lzw",
        "nodata": nodata,
        "height": array.shape[0],
        "width": array.shape[1],
    })
    with rasterio.open(out_path, "w", **prof) as dst:
        dst.write(array.astype(dtype), 1)
    return out_path


def filter_stream_connected_blobs(
    candidate_mask: np.ndarray,
    stream_mask: np.ndarray,
    pixel_size_m: float = 10.0,
    proximity_m: float = 100.0,
    min_pixels: int = 20
) -> Tuple[np.ndarray, int]:
    """
    Filter candidate binary mask:
    - Retain only connected component blobs with area >= min_pixels
    - Retain only blobs that touch or lie within proximity_m of the stream network.
    """
    if np.sum(candidate_mask) == 0:
        return np.zeros_like(candidate_mask, dtype=np.uint8), 0

    dist_to_stream = distance_transform_edt(stream_mask == 0) * pixel_size_m
    near_stream = dist_to_stream <= proximity_m

    labeled, num_features = label(candidate_mask)
    if num_features == 0:
        return np.zeros_like(candidate_mask, dtype=np.uint8), 0

    counts = np.bincount(labeled.ravel())
    retained = np.zeros_like(candidate_mask, dtype=np.uint8)
    blob_count = 0

    for feat_id in range(1, num_features + 1):
        if counts[feat_id] < min_pixels:
            continue
        blob = (labeled == feat_id)
        if np.any(blob & near_stream):
            retained[blob] = 1
            blob_count += 1

    return retained, blob_count


def load_s1_features(
    stack_dir: Path,
    s1_cache_dir: Path,
    post_vv_path: Path
) -> Dict[str, np.ndarray]:
    """
    Load S1 multi-temporal pre-stack, compute ascending z-scores,
    and load descending orbit 19 log-ratio.
    """
    pre_dates = ['2026-06-29', '2026-07-11', '2026-07-23', '2026-08-04', '2026-08-16']
    vv_stack = []
    for d in pre_dates:
        f_p = stack_dir / f"s1_{d}.tif"
        if not f_p.exists():
            raise FileNotFoundError(f"Missing S1 stack file: {f_p}")
        with rasterio.open(f_p) as s:
            vv_stack.append(10.0 * np.log10(np.maximum(s.read(1), 1e-5)))

    vv_mean = np.mean(vv_stack, axis=0)
    vv_std = np.maximum(np.std(vv_stack, axis=0), 0.2)

    with rasterio.open(post_vv_path) as s:
        post_vv = s.read(1)
    if np.nanmin(post_vv) < 0.0:
        post_vv_db = post_vv
    else:
        post_vv_db = 10.0 * np.log10(np.maximum(post_vv, 1e-5))
    z_vv_asc_event = (post_vv_db - vv_mean) / vv_std

    # Ascending Control z-score (using 4 earlier scenes as baseline, 5th scene as observation)
    ctrl_vv_mean = np.mean(vv_stack[:4], axis=0)
    ctrl_vv_std = np.maximum(np.std(vv_stack[:4], axis=0), 0.2)
    z_vv_asc_ctrl = (vv_stack[4] - ctrl_vv_mean) / ctrl_vv_std

    # Descending Orbit 19 log-ratio
    o19_file = s1_cache_dir / "o19_desc.npz"
    if o19_file.exists():
        o19_data = np.load(o19_file)
        o19_pre_vv = o19_data['vv_pre']
        o19_post_vv = o19_data['vv_post']
        o19_lr_event = (
            10.0 * np.log10(np.maximum(o19_post_vv, 1e-5)) -
            10.0 * np.log10(np.maximum(o19_pre_vv, 1e-5))
        )
    else:
        o19_lr_event = np.zeros_like(post_vv_db)

    return {
        "z_vv_asc_event": z_vv_asc_event,
        "z_vv_asc_ctrl": z_vv_asc_ctrl,
        "o19_lr_event": o19_lr_event,
        "post_vv": post_vv
    }


def run_layer2(
    interim_dir: str = "data/interim",
    control_interim_dir: str = "data/control/interim",
    s2_cache_dir: str = "data/interim/s2_cache",
    s1_cache_dir: str = "data/interim/s1_cache",
    s1_stack_dir: str = "data/raw/s1_stack",
    osm_waterways_path: str = "data/raw/osm/osm_waterways.geojson",
    osm_buildings_path: str = "data/raw/osm/osm_buildings.geojson",
    out_dir: str = "data/processed",
    control_out_dir: Optional[str] = None,
    false_alarm_rate_pct: float = 1.0,
    max_hand_corridor_m: float = 40.0,
    stream_proximity_m: float = 100.0,
    min_area_pixels: int = 20,
    cloud_dilation_buffer_m: float = 60.0,
    simplify_tol_m: float = 8.0,
    reach_length_m: float = 250.0,
    inferred_hand_percentile: float = 90.0,
    inferred_min_observed_pixels: int = 20,
    building_buffer_m: float = 10.0,
    intact_min_post_ndvi: float = 0.40,
    intact_max_abs_d_ndvi: float = 0.20
) -> Dict[str, Any]:

    in_path = Path(interim_dir)
    ctrl_path = Path(control_interim_dir)
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    if control_out_dir is None:
        ctrl_out_path = out_path.parent / "control" / "processed"
    else:
        ctrl_out_path = Path(control_out_dir)
    ctrl_out_path.mkdir(parents=True, exist_ok=True)

    logger.info("=== LAYER 2: SENTINEL-2 OPTICAL PRIMARY + S1 FALLBACK DETECTOR ===")

    # 1. Load terrain and hydrological masks
    with rasterio.open(in_path / "hand.tif") as f_hand, \
         rasterio.open(in_path / "shadow_layover_mask.tif") as f_shadow, \
         rasterio.open(in_path / "nodata_mask.tif") as f_nodata:

        hand = f_hand.read(1)
        shadow_mask = f_shadow.read(1)
        nodata_mask = f_nodata.read(1)
        ref_profile = f_hand.profile.copy()
        transform_mat = f_hand.transform
        crs = f_hand.crs
        h, w = hand.shape
        dx, dy = abs(transform_mat.a), abs(transform_mat.e)

    stream_mask_file = in_path / "stream_mask.tif"
    if stream_mask_file.exists():
        with rasterio.open(stream_mask_file) as f_st:
            stream_mask = f_st.read(1)
    else:
        stream_mask = (hand <= 5.0).astype(np.uint8)

    pixel_area_m2 = dx * dy
    pixel_area_km2 = pixel_area_m2 / 1e6
    hand_corridor = (hand <= max_hand_corridor_m) & (hand >= 0)

    # 2. Prepare Sentinel-2 composites & indices
    logger.info("Preparing Sentinel-2 multi-temporal composites and cloud masking...")
    s2_data = prepare_s2_event_and_control_composites(
        cache_dir=s2_cache_dir,
        dilation_buffer_m=cloud_dilation_buffer_m,
        pixel_size_m=dx
    )

    pre_comp = s2_data['pre_composite']
    post_comp = s2_data['post_composite']
    d_ndvi_event = s2_data['d_ndvi_event']
    d_bsi_event = s2_data['d_bsi_event']
    s2_event_valid = s2_data['s2_event_valid']

    d_ndvi_ctrl = s2_data['d_ndvi_ctrl']
    d_bsi_ctrl = s2_data['d_bsi_ctrl']
    s2_ctrl_valid = s2_data['s2_ctrl_valid']

    # 3. Load Sentinel-1 features (Ascending stack z-scores & Descending O19 log-ratio)
    logger.info("Loading Sentinel-1 SAR features for cloudy-area fallback...")
    s1_data = load_s1_features(
        stack_dir=Path(s1_stack_dir),
        s1_cache_dir=Path(s1_cache_dir),
        post_vv_path=Path("data/raw/s1/post.tif") if Path("data/raw/s1/post.tif").exists() else (in_path / "post_vv.tif")
    )
    z_vv_asc_event = s1_data['z_vv_asc_event']
    z_vv_asc_ctrl = s1_data['z_vv_asc_ctrl']
    o19_lr_event = s1_data['o19_lr_event']
    post_vv = s1_data['post_vv']

    # 4. Class 1 Baseline: Pre-event Permanent Water / River-bed (Pre NDWI + OSM)
    logger.info("Detecting baseline pre-event permanent water / river-bed (Pre NDWI + OSM)...")
    perm_water_raw, _ = detect_permanent_water(
        pre_vv=post_vv,
        hand=hand,
        shadow_mask=shadow_mask,
        osm_waterways_path=osm_waterways_path,
        transform_matrix=transform_mat,
        crs=crs,
        hand_corridor_m=15.0,
        pre_ndwi=pre_comp['ndwi']
    )

    # Compute adaptive thresholds from CONTROL pair inside active HAND corridor
    logger.info("Computing adaptive thresholds from CONTROL pair inside HAND corridor...")
    t_d_ndvi, t_d_bsi = compute_s2_control_thresholds(
        d_ndvi_ctrl=d_ndvi_ctrl,
        d_bsi_ctrl=d_bsi_ctrl,
        ctrl_valid=s2_ctrl_valid,
        hand=hand,
        max_hand_m=max_hand_corridor_m,
        false_alarm_rate_pct=false_alarm_rate_pct
    )

    t_channel = compute_in_channel_control_threshold(
        in_channel_change_ctrl=s2_data['in_channel_change_ctrl'],
        perm_water_mask=perm_water_raw,
        ctrl_valid=s2_ctrl_valid,
        hand=hand,
        max_hand_m=max_hand_corridor_m,
        false_alarm_rate_pct=false_alarm_rate_pct
    )

    # S2 Change vector magnitude for built-up footprints (B2, B3, B4, B8, B11, B12)
    band_keys = ['b02', 'b03', 'b04', 'b08', 'b11', 'b12']
    sq_ev = sum([((post_comp[b] - pre_comp[b]) / 10000.0) ** 2 for b in band_keys])
    cvm_ev = np.sqrt(sq_ev).astype(np.float32)

    sq_ctrl = sum([((s2_data['ctrl_post_composite'][b] - pre_comp[b]) / 10000.0) ** 2 for b in band_keys])
    cvm_ctrl = np.sqrt(sq_ctrl).astype(np.float32)

    # Rasterize pre-event OSM building footprints (+ buffer)
    builtup_mask = np.zeros((h, w), dtype=np.uint8)
    if Path(osm_buildings_path).exists():
        b_gdf = gpd.read_file(osm_buildings_path)
        if not b_gdf.empty:
            if b_gdf.crs != crs:
                b_gdf = b_gdf.to_crs(crs)
            b_geoms = [geom.buffer(building_buffer_m) for geom in b_gdf.geometry if geom is not None and not geom.is_empty]
            if b_geoms:
                builtup_mask = rasterize(b_geoms, out_shape=(h, w), transform=transform_mat, fill=0, default_value=1, dtype=np.uint8)

    t_builtup = compute_builtup_control_threshold(
        cvm_ctrl=cvm_ctrl,
        builtup_mask=builtup_mask,
        ctrl_valid=s2_ctrl_valid,
        hand=hand,
        max_hand_m=max_hand_corridor_m,
        false_alarm_rate_pct=false_alarm_rate_pct
    )

    t_z_asc = compute_s1_zscore_control_threshold(
        z_vv_asc_ctrl=z_vv_asc_ctrl,
        hand=hand,
        shadow_mask=shadow_mask,
        nodata_mask=nodata_mask,
        max_hand_m=max_hand_corridor_m,
        false_alarm_rate_pct=false_alarm_rate_pct
    )
    t_lr_o19 = -3.5  # dB threshold for descending S1

    print("\n--- THRESHOLDS USED (FROM CONTROL IN HAND CORRIDOR) ---")
    print(f"  Sentinel-2 ΔNDVI threshold:          {t_d_ndvi:.4f} ({false_alarm_rate_pct}th percentile)")
    print(f"  Sentinel-2 ΔBSI threshold:           +{t_d_bsi:.4f} ({100.0 - false_alarm_rate_pct}th percentile)")
    print(f"  In-channel S2 change vector threshold: {t_channel:.4f} ({100.0 - false_alarm_rate_pct}th percentile)")
    print(f"  Built-up S2 change vector threshold:   {t_builtup:.4f} ({100.0 - false_alarm_rate_pct}th percentile)")
    print(f"  Sentinel-1 Ascending z-score threshold: {t_z_asc:.4f}")
    print(f"  Sentinel-1 Descending O19 log-ratio threshold: {t_lr_o19:.4f} dB")

    # 5. Class 2: Flood / Debris Affected (EVENT: Valley + In-Channel Scour + Built-up)
    logger.info("Detecting Class 2: Flood / Debris Affected on EVENT (Valley + In-Channel + Built-up)...")
    s2_ev_cand = s2_event_valid & ((d_ndvi_event < t_d_ndvi) | (d_bsi_event > t_d_bsi)) & hand_corridor
    ch_ev_cand = s2_event_valid & (perm_water_raw == 1) & hand_corridor & (s2_data['in_channel_change_event'] > t_channel)
    s1_ev_cand = (~s2_event_valid) & ((z_vv_asc_event < t_z_asc) | (o19_lr_event < t_lr_o19)) & hand_corridor & (shadow_mask == 0) & (nodata_mask == 0)
    b_ev_cand = s2_event_valid & (builtup_mask == 1) & hand_corridor & (cvm_ev > t_builtup)

    ev_cand_total = (s2_ev_cand | ch_ev_cand | s1_ev_cand | b_ev_cand).astype(np.uint8)

    aff_ev_clean, n_blobs_ev = filter_stream_connected_blobs(
        candidate_mask=ev_cand_total,
        stream_mask=stream_mask,
        pixel_size_m=dx,
        proximity_m=stream_proximity_m,
        min_pixels=min_area_pixels
    )

    # In-channel changed pixels become Class 2 (sub-label "channel")
    # Built-up affected pixels (sub-label "built-up")
    # Unchanged baseline water remains Class 1
    ch_ev_affected = (perm_water_raw == 1) & (aff_ev_clean == 1)
    b_ev_affected = (builtup_mask == 1) & (aff_ev_clean == 1)
    perm_water_unchanged = (perm_water_raw == 1) & (aff_ev_clean != 1)

    perm_count = int(np.sum(perm_water_unchanged == 1))
    perm_km2 = round(perm_count * pixel_area_km2, 4)

    # Source attribution: S2 vs S1
    source_mask_ev = np.zeros((h, w), dtype=np.uint8)
    source_mask_ev[s2_event_valid] = 1  # 1: S2
    source_mask_ev[~s2_event_valid] = 2  # 2: S1

    ev_s2_count = int(np.sum((aff_ev_clean == 1) & (source_mask_ev == 1)))
    ev_s1_count = int(np.sum((aff_ev_clean == 1) & (source_mask_ev == 2)))
    ev_aff_count = int(np.sum(aff_ev_clean == 1))

    ev_s2_km2 = round(ev_s2_count * pixel_area_km2, 4)
    ev_s1_km2 = round(ev_s1_count * pixel_area_km2, 4)
    ev_aff_km2 = round(ev_aff_count * pixel_area_km2, 4)

    # 5b. Class 3: Inferred Flooded Corridor (HAND-based hydraulic fill along stream reaches)
    logger.info("Computing Class 3: Inferred Flood Corridor via reach-based hydraulic fill (EVENT)...")
    inferred_ev_clean, inferred_ev_stats = compute_inferred_flood_corridor(
        hand=hand,
        stream_mask=stream_mask,
        observed_class2_mask=(aff_ev_clean == 1),
        pixel_size_m=dx,
        reach_length_m=reach_length_m,
        hand_percentile=inferred_hand_percentile,
        min_observed_pixels=inferred_min_observed_pixels,
        touch_distance_m=stream_proximity_m,
        max_hand_corridor_m=max_hand_corridor_m,
        post_ndvi=post_comp['ndvi'],
        d_ndvi=d_ndvi_event,
        intact_min_post_ndvi=intact_min_post_ndvi,
        intact_max_abs_d_ndvi=intact_max_abs_d_ndvi
    )
    ev_inf_km2 = inferred_ev_stats["inferred_km2"]
    ev_inf_count = inferred_ev_stats["inferred_pixels"]

    # 6. Evaluate CONTROL pair with the exact same detector
    logger.info("Evaluating CONTROL pair with the exact same multi-sensor detector...")
    s2_ctrl_cand = s2_ctrl_valid & ((d_ndvi_ctrl < t_d_ndvi) | (d_bsi_ctrl > t_d_bsi)) & hand_corridor
    ch_ctrl_cand = s2_ctrl_valid & (perm_water_raw == 1) & hand_corridor & (s2_data['in_channel_change_ctrl'] > t_channel)
    s1_ctrl_cand = (~s2_ctrl_valid) & (z_vv_asc_ctrl < t_z_asc) & hand_corridor & (shadow_mask == 0) & (nodata_mask == 0)
    b_ctrl_cand = s2_ctrl_valid & (builtup_mask == 1) & hand_corridor & (cvm_ctrl > t_builtup)

    ctrl_cand_total = (s2_ctrl_cand | ch_ctrl_cand | s1_ctrl_cand | b_ctrl_cand).astype(np.uint8)

    aff_ctrl_clean, n_blobs_ctrl = filter_stream_connected_blobs(
        candidate_mask=ctrl_cand_total,
        stream_mask=stream_mask,
        pixel_size_m=dx,
        proximity_m=stream_proximity_m,
        min_pixels=min_area_pixels
    )

    ctrl_s2_count = int(np.sum((aff_ctrl_clean == 1) & s2_ctrl_valid))
    ctrl_s1_count = int(np.sum((aff_ctrl_clean == 1) & (~s2_ctrl_valid)))
    ctrl_aff_count = int(np.sum(aff_ctrl_clean == 1))

    ctrl_s2_km2 = round(ctrl_s2_count * pixel_area_km2, 4)
    ctrl_s1_km2 = round(ctrl_s1_count * pixel_area_km2, 4)
    ctrl_aff_km2 = round(ctrl_aff_count * pixel_area_km2, 4)

    logger.info("Computing Class 3: Inferred Flood Corridor via reach-based hydraulic fill (CONTROL)...")
    inferred_ctrl_clean, inferred_ctrl_stats = compute_inferred_flood_corridor(
        hand=hand,
        stream_mask=stream_mask,
        observed_class2_mask=(aff_ctrl_clean == 1),
        pixel_size_m=dx,
        reach_length_m=reach_length_m,
        hand_percentile=inferred_hand_percentile,
        min_observed_pixels=inferred_min_observed_pixels,
        touch_distance_m=stream_proximity_m,
        max_hand_corridor_m=max_hand_corridor_m,
        post_ndvi=s2_data['ctrl_post_composite']['ndvi'],
        d_ndvi=d_ndvi_ctrl,
        intact_min_post_ndvi=intact_min_post_ndvi,
        intact_max_abs_d_ndvi=intact_max_abs_d_ndvi
    )
    ctrl_inf_km2 = inferred_ctrl_stats["inferred_km2"]
    ctrl_inf_count = inferred_ctrl_stats["inferred_pixels"]

    logger.info(f"EVENT Affected:   {ev_aff_km2} km² (S2: {ev_s2_km2} km², S1: {ev_s1_km2} km²), Inferred: {ev_inf_km2} km²")
    logger.info(f"CONTROL Affected: {ctrl_aff_km2} km² (S2: {ctrl_s2_km2} km², S1: {ctrl_s1_km2} km²), Inferred: {ctrl_inf_km2} km²")

    # 7. Synthesize Hazard Rasters (0=Background, 1=Permanent Water, 2=Flood/Debris Affected, 3=Inferred Flooded)
    hazard_raster = np.zeros((h, w), dtype=np.uint8)
    hazard_raster[perm_water_unchanged == 1] = 1
    hazard_raster[inferred_ev_clean == 1] = 3
    hazard_raster[aff_ev_clean == 1] = 2  # class 2 preserved unconditionally

    # Save EVENT GeoTIFFs
    out_tif = str(out_path / "hazard_classes.tif")
    save_single_band_geotiff(out_tif, hazard_raster, ref_profile, dtype="uint8", nodata=0)

    out_source_tif = str(out_path / "source_mask.tif")
    save_single_band_geotiff(out_source_tif, source_mask_ev, ref_profile, dtype="uint8", nodata=0)

    # Vectorize EVENT GeoJSON
    out_geojson = str(out_path / "hazard_polygons.geojson")
    vec_summary = vectorize_hazard_classes(
        hazard_raster=hazard_raster,
        transform_matrix=transform_mat,
        crs=crs,
        out_geojson_path=out_geojson,
        simplify_tolerance_m=simplify_tol_m,
        min_area_m2=pixel_area_m2 * min_area_pixels,
        channel_affected_mask=ch_ev_affected,
        builtup_affected_mask=b_ev_affected
    )

    # Render EVENT Quicklook (Full AOI + Syabru Besi 4x4 km zoom with S2 post true colour + affected outline)
    out_quicklook = str(out_path / "quicklook_layer2.png")
    stats_dict = {
        "perm_water_km2": perm_km2,
        "affected_km2": ev_aff_km2,
        "inferred_km2": ev_inf_km2
    }
    render_layer2_quicklook(
        post_vv=post_vv,
        hazard_raster=hazard_raster,
        output_png_path=out_quicklook,
        stats=stats_dict,
        post_vis=post_comp['vis'],
        zoom_center=(992, 431)
    )

    # Control Outputs
    ctrl_hazard_raster = np.zeros((h, w), dtype=np.uint8)
    ctrl_hazard_raster[(perm_water_raw == 1) & (aff_ctrl_clean != 1)] = 1
    ctrl_hazard_raster[inferred_ctrl_clean == 1] = 3
    ctrl_hazard_raster[aff_ctrl_clean == 1] = 2

    ctrl_out_tif = str(ctrl_out_path / "hazard_classes.tif")
    save_single_band_geotiff(ctrl_out_tif, ctrl_hazard_raster, ref_profile, dtype="uint8", nodata=0)
    ctrl_out_geojson = str(ctrl_out_path / "hazard_polygons.geojson")
    vectorize_hazard_classes(
        hazard_raster=ctrl_hazard_raster,
        transform_matrix=transform_mat,
        crs=crs,
        out_geojson_path=ctrl_out_geojson,
        simplify_tolerance_m=simplify_tol_m,
        min_area_m2=pixel_area_m2 * min_area_pixels,
        channel_affected_mask=(aff_ctrl_clean == 1) & (perm_water_raw == 1),
        builtup_affected_mask=(aff_ctrl_clean == 1) & (builtup_mask == 1)
    )
    ctrl_quicklook = str(ctrl_out_path / "quicklook_layer2.png")
    render_layer2_quicklook(
        post_vv=post_vv,
        hazard_raster=ctrl_hazard_raster,
        output_png_path=ctrl_quicklook,
        stats={"perm_water_km2": perm_km2, "affected_km2": ctrl_aff_km2, "inferred_km2": ctrl_inf_km2},
        post_vis=post_comp['vis'],
        zoom_center=(992, 431)
    )

    # Summary dictionary
    l2_summary = {
        "status": "COMPLETED",
        "scenes_used": s2_data['scenes_used'],
        "grid_shape": (h, w),
        "pixel_size_m": (dx, dy),
        "thresholds_used": {
            "s2_d_ndvi": round(float(t_d_ndvi), 4),
            "s2_d_bsi": round(float(t_d_bsi), 4),
            "s2_in_channel_cvm": round(float(t_channel), 4),
            "s2_builtup_cvm": round(float(t_builtup), 4),
            "s1_z_vv_asc": round(float(t_z_asc), 4),
            "s1_lr_o19_db": round(float(t_lr_o19), 2),
            "false_alarm_rate_pct": float(false_alarm_rate_pct),
            "max_hand_corridor_m": float(max_hand_corridor_m),
            "stream_proximity_m": float(stream_proximity_m),
            "min_area_pixels": int(min_area_pixels),
            "cloud_dilation_buffer_m": float(cloud_dilation_buffer_m),
            "reach_length_m": float(reach_length_m),
            "inferred_hand_percentile": float(inferred_hand_percentile),
            "inferred_min_observed_pixels": int(inferred_min_observed_pixels),
            "building_buffer_m": float(building_buffer_m),
            "intact_min_post_ndvi": float(intact_min_post_ndvi),
            "intact_max_abs_d_ndvi": float(intact_max_abs_d_ndvi)
        },
        "areas_km2": {
            "class_1_permanent_water": perm_km2,
            "event_total_affected": ev_aff_km2,
            "event_channel_affected": round(int(np.sum(ch_ev_affected)) * pixel_area_km2, 4),
            "event_builtup_affected": round(int(np.sum(b_ev_affected)) * pixel_area_km2, 4),
            "event_s2_affected": ev_s2_km2,
            "event_s1_affected": ev_s1_km2,
            "event_inferred_affected": ev_inf_km2,
            "control_total_affected": ctrl_aff_km2,
            "control_s2_affected": ctrl_s2_km2,
            "control_s1_affected": ctrl_s1_km2,
            "control_inferred_affected": ctrl_inf_km2
        },
        "pixel_counts": {
            "permanent_water": perm_count,
            "event_affected": ev_aff_count,
            "event_s2": ev_s2_count,
            "event_s1": ev_s1_count,
            "event_inferred": ev_inf_count,
            "control_affected": ctrl_aff_count,
            "control_s2": ctrl_s2_count,
            "control_s1": ctrl_s1_count,
            "control_inferred": ctrl_inf_count
        },
        "outputs": {
            "hazard_raster": out_tif,
            "source_mask": out_source_tif,
            "hazard_polygons": out_geojson,
            "quicklook": out_quicklook,
            "quicklook_syabrubesi": out_quicklook.replace("quicklook_layer2.png", "quicklook_syabrubesi.png"),
            "control_hazard_raster": ctrl_out_tif,
            "control_quicklook": ctrl_quicklook
        }
    }

    out_json = str(out_path / "l2_stats.json")
    with open(out_json, "w") as f:
        json.dump(l2_summary, f, indent=2)

    ctrl_json = str(ctrl_out_path / "l2_stats.json")
    with open(ctrl_json, "w") as f:
        json.dump(l2_summary, f, indent=2)

    return l2_summary


def main():
    parser = argparse.ArgumentParser(description="Run Layer 2 Final Sentinel-2 + Sentinel-1 Detector")
    parser.add_argument("--interim-dir", default="data/interim", help="Path to interim directory")
    parser.add_argument("--control-interim-dir", default="data/control/interim", help="Path to control interim directory")
    parser.add_argument("--s2-cache-dir", default="data/interim/s2_cache", help="Path to S2 cache directory")
    parser.add_argument("--s1-cache-dir", default="data/interim/s1_cache", help="Path to S1 cache directory")
    parser.add_argument("--s1-stack-dir", default="data/raw/s1_stack", help="Path to S1 stack directory")
    parser.add_argument("--osm-waterways", default="data/raw/osm/osm_waterways.geojson", help="Path to OSM waterways")
    parser.add_argument("--osm-buildings", default="data/raw/osm/osm_buildings.geojson", help="Path to OSM buildings")
    parser.add_argument("--out-dir", default="data/processed", help="Path to output directory")
    parser.add_argument("--config", help="Optional test YAML configuration")

    args = parser.parse_args()

    false_alarm_rate_pct = 1.0
    max_hand_corridor_m = 40.0
    stream_proximity_m = 100.0
    min_area_pixels = 20
    cloud_dilation_buffer_m = 60.0
    simplify_tol_m = 8.0
    reach_length_m = 250.0
    inferred_hand_percentile = 90.0
    inferred_min_observed_pixels = 20
    building_buffer_m = 10.0
    intact_min_post_ndvi = 0.40
    intact_max_abs_d_ndvi = 0.20

    if args.config and os.path.exists(args.config):
        with open(args.config, "r") as f:
            cfg = yaml.safe_load(f)
        det_cfg = cfg.get("detection", cfg.get("l2_detection", {}))
        false_alarm_rate_pct = float(det_cfg.get("false_alarm_rate_pct", false_alarm_rate_pct))
        max_hand_corridor_m = float(det_cfg.get("max_hand_corridor_m", max_hand_corridor_m))
        stream_proximity_m = float(det_cfg.get("stream_proximity_m", stream_proximity_m))
        min_area_pixels = int(det_cfg.get("min_area_pixels", min_area_pixels))
        cloud_dilation_buffer_m = float(det_cfg.get("cloud_dilation_buffer_m", cloud_dilation_buffer_m))
        simplify_tol_m = float(det_cfg.get("simplify_tolerance_m", simplify_tol_m))
        reach_length_m = float(det_cfg.get("reach_length_m", reach_length_m))
        inferred_hand_percentile = float(det_cfg.get("inferred_hand_percentile", inferred_hand_percentile))
        inferred_min_observed_pixels = int(det_cfg.get("inferred_min_observed_pixels", inferred_min_observed_pixels))
        building_buffer_m = float(det_cfg.get("building_buffer_m", building_buffer_m))
        intact_min_post_ndvi = float(det_cfg.get("intact_min_post_ndvi", intact_min_post_ndvi))
        intact_max_abs_d_ndvi = float(det_cfg.get("intact_max_abs_d_ndvi", intact_max_abs_d_ndvi))

    results = run_layer2(
        interim_dir=args.interim_dir,
        control_interim_dir=args.control_interim_dir,
        s2_cache_dir=args.s2_cache_dir,
        s1_cache_dir=args.s1_cache_dir,
        s1_stack_dir=args.s1_stack_dir,
        osm_waterways_path=args.osm_waterways,
        osm_buildings_path=args.osm_buildings,
        out_dir=args.out_dir,
        false_alarm_rate_pct=false_alarm_rate_pct,
        max_hand_corridor_m=max_hand_corridor_m,
        stream_proximity_m=stream_proximity_m,
        min_area_pixels=min_area_pixels,
        cloud_dilation_buffer_m=cloud_dilation_buffer_m,
        simplify_tol_m=simplify_tol_m,
        reach_length_m=reach_length_m,
        inferred_hand_percentile=inferred_hand_percentile,
        inferred_min_observed_pixels=inferred_min_observed_pixels,
        building_buffer_m=building_buffer_m,
        intact_min_post_ndvi=intact_min_post_ndvi,
        intact_max_abs_d_ndvi=intact_max_abs_d_ndvi
    )

    print("\n================== FINAL LAYER 2 DETECTION SUMMARY ==================")
    print(f"Sentinel-2 Scenes Pre:  {[s['scene_id'][:35] for s in results['scenes_used']['pre']]}")
    print(f"Sentinel-2 Scenes Post: {[s['scene_id'][:35] for s in results['scenes_used']['post']]}")
    print(f"Sentinel-2 Scenes Ctrl: {[s['scene_id'][:35] for s in results['scenes_used']['control_post']]}")
    print(f"Thresholds: ΔNDVI < {results['thresholds_used']['s2_d_ndvi']:.4f}, ΔBSI > +{results['thresholds_used']['s2_d_bsi']:.4f}, S1 z < {results['thresholds_used']['s1_z_vv_asc']:.4f}, S1 O19 < {results['thresholds_used']['s1_lr_o19_db']} dB")
    print(f"Permanent Water: {results['areas_km2']['class_1_permanent_water']} km²")
    print(f"EVENT Affected:   {results['areas_km2']['event_total_affected']} km² (S2: {results['areas_km2']['event_s2_affected']} km², S1: {results['areas_km2']['event_s1_affected']} km²)")
    print(f"Inferred Flooded: EVENT {results['areas_km2']['event_inferred_affected']} km² vs CONTROL {results['areas_km2']['control_inferred_affected']} km²")
    print(f"CONTROL Affected: {results['areas_km2']['control_total_affected']} km² (S2: {results['areas_km2']['control_s2_affected']} km², S1: {results['areas_km2']['control_s1_affected']} km²)")
    print(f"Quicklook: {results['outputs']['quicklook']}")


if __name__ == "__main__":
    main()
