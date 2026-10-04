"""
Layer 1 Preprocessing Orchestrator.
Processes raw Sentinel-1 RTC pairs, resamples Copernicus DEM-30,
calculates terrain metrics, HAND, shadow/layover masks, and exports interim GeoTIFFs.
"""

import os
import gc
import json
import logging
import argparse
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
import numpy as np
import rasterio
import yaml

from .radiometry import check_and_convert_to_db, compute_log_ratio
from .speckle import apply_lee_filter
from .grid import check_grid_identity, align_raster_to_reference, resample_dem_to_grid
from .terrain import compute_slope_aspect, compute_shadow_layover_mask
from .hand import compute_hand
from .quicklook import render_quicklook

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("layer1_preprocessing")


def save_single_band_geotiff(
    out_path: str,
    array: np.ndarray,
    ref_profile: Dict[str, Any],
    dtype: str = "float32",
    nodata: Optional[float] = None
) -> str:
    """Save 2D array as compressed single-band GeoTIFF on reference grid."""
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


def run_layer1(
    pre_path: str,
    post_path: str,
    dem_path: str,
    meta_path: Optional[str] = None,
    out_dir: str = "data/interim",
    window_size: int = 5,
    drainage_threshold: int = 1000,
    look_angle_deg: float = 38.0,
    orbit_heading_deg: float = 350.0,
    dem_buffer_km: float = 10.0
) -> Dict[str, Any]:
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    logger.info("=== LAYER 1: STARTING PREPROCESSING ===")
    logger.info(f"Pre-event S1:  {pre_path}")
    logger.info(f"Post-event S1: {post_path}")
    logger.info(f"DEM:           {dem_path}")
    logger.info(f"Output Dir:    {out_dir}")

    # Read metadata if available
    meta = {}
    if meta_path and os.path.exists(meta_path):
        with open(meta_path, "r") as f:
            meta = json.load(f)
        logger.info(f"Loaded metadata from {meta_path}")

    # 1. Inspect grid and shape
    with rasterio.open(pre_path) as src_pre, rasterio.open(post_path) as src_post:
        is_grid_identical, grid_details = check_grid_identity(src_pre, src_post)
        pre_profile = src_pre.profile.copy()
        pre_transform = src_pre.transform
        pre_crs = src_pre.crs
        h, w = src_pre.shape
        dx, dy = abs(pre_transform.a), abs(pre_transform.e)

        logger.info(f"S1 Input Shape: (height={h}, width={w}) -> {w}x{h} grid at {dx:.1f}m resolution")
        logger.info(f"Grid identical: {is_grid_identical}")

        # Read bands: Band 1 = VV, Band 2 = VH
        pre_b1 = src_pre.read(1)
        pre_b2 = src_pre.read(2)
        nd_pre = src_pre.nodata

        if is_grid_identical:
            post_b1 = src_post.read(1)
            post_b2 = src_post.read(2)
            nd_post = src_post.nodata
            reprojected = False
        else:
            logger.info("Post grid differs from Pre; aligning post to pre grid...")
            aligned_post = align_raster_to_reference(post_path, pre_profile)
            post_b1 = aligned_post[0]
            post_b2 = aligned_post[1]
            nd_post = nd_pre
            reprojected = True

    # 2. Radiometric check and unclipped conversion to dB
    pre_vv_db, pre_vv_conv, stats_pre_vv = check_and_convert_to_db(pre_b1, nodata=nd_pre)
    pre_vh_db, pre_vh_conv, stats_pre_vh = check_and_convert_to_db(pre_b2, nodata=nd_pre)
    post_vv_db, post_vv_conv, stats_post_vv = check_and_convert_to_db(post_b1, nodata=nd_post)
    post_vh_db, post_vh_conv, stats_post_vh = check_and_convert_to_db(post_b2, nodata=nd_post)

    logger.info(f"Pre VV dB:  min={stats_pre_vv['min']:.2f}, med={stats_pre_vv['median']:.2f}, max={stats_pre_vv['max']:.2f}")
    logger.info(f"Pre VH dB:  min={stats_pre_vh['min']:.2f}, med={stats_pre_vh['median']:.2f}, max={stats_pre_vh['max']:.2f}")
    logger.info(f"Post VV dB: min={stats_post_vv['min']:.2f}, med={stats_post_vv['median']:.2f}, max={stats_post_vv['max']:.2f}")
    logger.info(f"Post VH dB: min={stats_post_vh['min']:.2f}, med={stats_post_vh['median']:.2f}, max={stats_post_vh['max']:.2f}")

    # 3. Speckle filter (Lee 5x5) - keeping raw copies
    logger.info(f"Applying Lee speckle filter (window={window_size}x{window_size})...")
    pre_vv_filt = apply_lee_filter(pre_vv_db, window_size=window_size)
    pre_vh_filt = apply_lee_filter(pre_vh_db, window_size=window_size)
    post_vv_filt = apply_lee_filter(post_vv_db, window_size=window_size)
    post_vh_filt = apply_lee_filter(post_vh_db, window_size=window_size)

    # 4. Log-ratio (post_dB - pre_dB)
    log_ratio_vv = compute_log_ratio(post_vv_filt, pre_vv_filt)
    log_ratio_vh = compute_log_ratio(post_vh_filt, pre_vh_filt)

    # 5. Load / Resample DEM and compute HAND on buffered DEM
    logger.info(f"Processing DEM with buffer (buffer={dem_buffer_km}km)...")
    from rasterio.warp import reproject, Resampling
    from rasterio.transform import from_bounds as tf_bounds

    buffered_dem_file = Path(dem_path).parent / "dem_buffered.tif"
    if dem_buffer_km > 0 and not buffered_dem_file.exists():
        from ..l0_ingestion.fetch_dem import fetch_dem
        # Derive lat/lon bbox from pre raster bounds
        from rasterio.warp import transform_bounds
        wgs_bounds = transform_bounds(src_pre.crs, "EPSG:4326", *src_pre.bounds)
        fetch_dem(list(wgs_bounds), out_dir=str(Path(dem_path).parent), buffer_km=dem_buffer_km)

    actual_dem_to_use = str(buffered_dem_file) if (dem_buffer_km > 0 and buffered_dem_file.exists()) else dem_path

    with rasterio.open(actual_dem_to_use) as src_dem_buf:
        if dem_buffer_km > 0:
            s1_bounds = src_pre.bounds
            buf_m = dem_buffer_km * 1000.0
            buf_bounds = (s1_bounds.left - buf_m, s1_bounds.bottom - buf_m, s1_bounds.right + buf_m, s1_bounds.top + buf_m)
            buf_w = int(round((buf_bounds[2] - buf_bounds[0]) / dx))
            buf_h = int(round((buf_bounds[3] - buf_bounds[1]) / dy))
            buf_transform = tf_bounds(*buf_bounds, buf_w, buf_h)

            dem_utm_buf = np.empty((buf_h, buf_w), dtype=np.float32)
            reproject(
                source=rasterio.band(src_dem_buf, 1),
                destination=dem_utm_buf,
                src_transform=src_dem_buf.transform,
                src_crs=src_dem_buf.crs,
                dst_transform=buf_transform,
                dst_crs=src_pre.crs,
                resampling=Resampling.bilinear
            )

            # Compute HAND on buffered DEM
            logger.info(f"Computing HAND on buffered DEM ({buf_w}x{buf_h} cells, drainage_threshold={drainage_threshold})...")
            hand_buf, stream_buf, hand_stats = compute_hand(
                elevation=dem_utm_buf,
                dx=dx,
                dy=dy,
                drainage_threshold=drainage_threshold
            )

            # Clip to S1 unbuffered grid
            r_start = int(round((buf_bounds[3] - s1_bounds.top) / dy))
            r_end = r_start + h
            c_start = int(round((s1_bounds.left - buf_bounds[0]) / dx))
            c_end = c_start + w

            hand = hand_buf[r_start:r_end, c_start:c_end]
            stream_mask = stream_buf[r_start:r_end, c_start:c_end]
            dem_aligned = dem_utm_buf[r_start:r_end, c_start:c_end]
            del dem_utm_buf, hand_buf, stream_buf
        else:
            dem_identical, _ = check_grid_identity(src_pre, src_dem_buf)
            if dem_identical:
                dem_aligned = src_dem_buf.read(1).astype(np.float32)
            else:
                dem_aligned = resample_dem_to_grid(actual_dem_to_use, pre_profile)

            logger.info("Computing HAND via D8 flow accumulation on unbuffered DEM...")
            hand, stream_mask, hand_stats = compute_hand(
                elevation=dem_aligned,
                dx=dx,
                dy=dy,
                drainage_threshold=drainage_threshold
            )

    # 6. Compute slope and aspect
    logger.info("Computing slope and aspect...")
    slope_deg, aspect_deg = compute_slope_aspect(dem_aligned, dx=dx, dy=dy)

    # 7. Shadow / layover mask
    logger.info("Computing shadow/layover mask...")
    shadow_layover_mask, shadow_stats = compute_shadow_layover_mask(
        slope_deg=slope_deg,
        aspect_deg=aspect_deg,
        look_angle_deg=look_angle_deg,
        orbit_heading_deg=orbit_heading_deg
    )

    # 8. Nodata mask
    nodata_mask = (
        ~np.isfinite(pre_vv_db) | ~np.isfinite(pre_vh_db) |
        ~np.isfinite(post_vv_db) | ~np.isfinite(post_vh_db) |
        ~np.isfinite(dem_aligned) | (dem_aligned <= -9999.0)
    ).astype(np.uint8)
    pct_nodata = float(np.sum(nodata_mask) / nodata_mask.size * 100.0)

    # 9. Save GeoTIFFs to interim dir
    logger.info(f"Saving interim GeoTIFFs to {out_dir}...")
    output_paths = {}
    save_specs = [
        ("pre_vv", pre_vv_filt, "float32", np.nan),
        ("pre_vh", pre_vh_filt, "float32", np.nan),
        ("post_vv", post_vv_filt, "float32", np.nan),
        ("post_vh", post_vh_filt, "float32", np.nan),
        ("pre_vv_raw", pre_vv_db, "float32", np.nan),
        ("pre_vh_raw", pre_vh_db, "float32", np.nan),
        ("post_vv_raw", post_vv_db, "float32", np.nan),
        ("post_vh_raw", post_vh_db, "float32", np.nan),
        ("log_ratio_vv", log_ratio_vv, "float32", np.nan),
        ("log_ratio_vh", log_ratio_vh, "float32", np.nan),
        ("slope", slope_deg, "float32", np.nan),
        ("hand", hand, "float32", np.nan),
        ("stream_mask", stream_mask, "uint8", 0),
        ("shadow_layover_mask", shadow_layover_mask, "uint8", 255),
        ("nodata_mask", nodata_mask, "uint8", 255),
    ]

    for name, arr, dtype, nd in save_specs:
        out_f = str(out_path / f"{name}.tif")
        save_single_band_geotiff(out_f, arr, pre_profile, dtype=dtype, nodata=nd)
        output_paths[name] = out_f

    # 11. Quick-look visualization
    quicklook_path = str(out_path / "quicklook_layer1.png")
    logger.info(f"Rendering quicklook diagnostic to {quicklook_path}...")
    render_quicklook(
        pre_vv_db=pre_vv_filt,
        post_vv_db=post_vv_filt,
        log_ratio_vv=log_ratio_vv,
        hand=hand,
        shadow_layover_mask=shadow_layover_mask,
        output_png_path=quicklook_path,
        title_suffix="SatFlood L1"
    )
    output_paths["quicklook_png"] = quicklook_path

    # Clean up arrays
    del pre_b1, pre_b2, post_b1, post_b2
    del pre_vv_filt, pre_vh_filt, post_vv_filt, post_vh_filt
    del log_ratio_vv, log_ratio_vh, dem_aligned, slope_deg, aspect_deg
    del hand, shadow_layover_mask, nodata_mask
    gc.collect()

    logger.info("=== LAYER 1: PREPROCESSING COMPLETE ===")
    return {
        "status": "COMPLETED",
        "input_paths": {
            "pre": pre_path,
            "post": post_path,
            "dem": dem_path,
            "meta": meta_path
        },
        "shape": (h, w),
        "grid_str": f"{w}x{h}",
        "dates": {
            "pre": meta.get("pre", {}).get("datetime", ""),
            "post": meta.get("post", {}).get("datetime", ""),
            "orbit": meta.get("post", {}).get("relative_orbit", None),
            "pass": meta.get("post", {}).get("orbit_direction", "").upper()
        },
        "db_stats": {
            "pre_vv": stats_pre_vv,
            "pre_vh": stats_pre_vh,
            "post_vv": stats_post_vv,
            "post_vh": stats_post_vh,
        },
        "shadow_layover_stats": shadow_stats,
        "hand_stats": hand_stats,
        "pct_nodata": round(pct_nodata, 4),
        "output_paths": output_paths
    }


def main():
    parser = argparse.ArgumentParser(description="Run Layer 1 Preprocessing")
    parser.add_argument("--pre", default="data/raw/s1/pre.tif", help="Path to pre S1 tif")
    parser.add_argument("--post", default="data/raw/s1/post.tif", help="Path to post S1 tif")
    parser.add_argument("--dem", default="data/raw/dem/dem.tif", help="Path to DEM tif")
    parser.add_argument("--meta", default="data/raw/s1/meta.json", help="Path to S1 meta json")
    parser.add_argument("--out-dir", default="data/interim", help="Output directory")
    parser.add_argument("--config", help="Optional test yaml config")

    args = parser.parse_args()

    # Default parameters
    window_size = 5
    drainage_threshold = 1000
    look_angle_deg = 38.0
    orbit_heading_deg = 350.0
    dem_buffer_km = 10.0

    if args.config and os.path.exists(args.config):
        with open(args.config, "r") as f:
            cfg = yaml.safe_load(f)
        p_cfg = cfg.get("preprocessing", {})
        window_size = int(p_cfg.get("filter_window_size", window_size))
        drainage_threshold = int(p_cfg.get("drainage_accumulation_threshold", drainage_threshold))
        look_angle_deg = float(p_cfg.get("look_angle_deg", look_angle_deg))
        orbit_heading_deg = float(p_cfg.get("orbit_heading_deg", orbit_heading_deg))
        dem_buffer_km = float(p_cfg.get("dem_buffer_km", dem_buffer_km))

    results = run_layer1(
        pre_path=args.pre,
        post_path=args.post,
        dem_path=args.dem,
        meta_path=args.meta,
        out_dir=args.out_dir,
        window_size=window_size,
        drainage_threshold=drainage_threshold,
        look_angle_deg=look_angle_deg,
        orbit_heading_deg=orbit_heading_deg,
        dem_buffer_km=dem_buffer_km
    )

    print("\n--- LAYER 1 SUMMARY ---")
    print(f"Input Shape: {results['grid_str']} (rows={results['shape'][0]}, cols={results['shape'][1]})")
    print(f"Dates: Pre {results['dates']['pre'][:10]} -> Post {results['dates']['post'][:10]} (Track {results['dates']['orbit']} {results['dates']['pass']})")
    print(f"Unclipped dB Stats:")
    for k, v in results['db_stats'].items():
        print(f"  {k}: min={v['min']:.2f}, med={v['median']:.2f}, max={v['max']:.2f}")
    print(f"Shadow/Layover: {results['shadow_layover_stats']['pct_masked']}% (Layover: {results['shadow_layover_stats']['pct_layover']}%, Shadow: {results['shadow_layover_stats']['pct_shadow']}%)")
    print(f"HAND Stats: min={results['hand_stats']['hand_min_m']}m, med={results['hand_stats']['hand_median_m']}m, max={results['hand_stats']['hand_max_m']}m (Streams: {results['hand_stats']['stream_cells']} cells)")
    print(f"Quick-look PNG: {results['output_paths']['quicklook_png']}")


if __name__ == "__main__":
    main()
