"""
End-to-End Orchestrator for Disaster Impact Assessment Pipeline (L0 - L5).
Executes L0 (Ingestion), L1 (Preprocessing), L2 (Detection), L4 (Damage Grading), and L5 (Routing).
"""

import sys
import os

# Clean proxy environment for direct external network access
for _k in ["http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY"]:
    os.environ.pop(_k, None)

import time
import json
import logging
import argparse
import shutil
import resource
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

import yaml
import numpy as np

import concurrent.futures
from src.l0_ingestion.run_l0 import run_layer0
from src.l0_ingestion.fetch_osm import fetch_osm
from src.l0_ingestion.fetch_dem import fetch_dem
from src.l0_ingestion.fetch_s1 import fetch_pair
from src.l0_ingestion.fetch_s2 import fetch_s2
from src.l5_routing.fetch_data import fetch_buffered_osm
from src.l1_preprocessing.run_l1 import run_layer1
from src.l2_detection.run_l2 import run_layer2
from src.l4_damage_grading.run_l4 import run_layer4
from src.l5_routing.run_l5 import run_layer5

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("main_pipeline")


def update_status_file(
    status_file: Path,
    stage: str,
    progress: float,
    elapsed_s: float,
    current_step: str,
    outputs: Optional[Dict[str, Any]] = None,
    metrics: Optional[Dict[str, Any]] = None,
    error: Optional[str] = None
):
    """Writes polling status file for UI/dashboard monitoring."""
    payload = {
        "timestamp": datetime.now().isoformat(),
        "stage": stage,
        "progress_pct": round(progress * 100, 1),
        "elapsed_seconds": round(elapsed_s, 2),
        "current_step": current_step,
        "outputs": outputs or {},
        "metrics": metrics or {}
    }
    if error:
        payload["error"] = error
    try:
        with open(status_file, "w") as f:
            json.dump(payload, f, indent=2)
    except Exception as e:
        logger.warning(f"Could not write status file: {e}")


def get_peak_ram_mb() -> float:
    """Returns peak resident set size (RSS) in MB."""
    # ru_maxrss is in kilobytes on Linux
    return round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0, 2)


def get_current_rss_mb() -> float:
    """Returns current resident set size (RSS) in MB from /proc/self/status."""
    try:
        with open("/proc/self/status") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    return round(float(line.split()[1]) / 1024.0, 2)
    except Exception:
        pass
    return get_peak_ram_mb()


def get_swap_used_mb() -> float:
    """Returns system swap used in MB from /proc/meminfo."""
    try:
        with open("/proc/meminfo") as f:
            lines = f.readlines()
        total, free = 0.0, 0.0
        for l in lines:
            if l.startswith("SwapTotal:"):
                total = float(l.split()[1])
            elif l.startswith("SwapFree:"):
                free = float(l.split()[1])
        return round((total - free) / 1024.0, 2)
    except Exception:
        return 0.0


def get_dir_size_mb(path: Path) -> float:
    """Returns total size of files in a directory in MB."""
    if not path.exists():
        return 0.0
    total_bytes = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
    return round(total_bytes / (1024.0 * 1024.0), 2)


def auto_utm_crs(bbox: List[float]) -> str:
    """Computes UTM EPSG CRS string from WGS84 bbox [min_lon, min_lat, max_lon, max_lat]."""
    center_lon = (bbox[0] + bbox[2]) / 2.0
    center_lat = (bbox[1] + bbox[3]) / 2.0
    zone = int((center_lon + 180) // 6) + 1
    if center_lat >= 0:
        return f"EPSG:{32600 + zone}"
    else:
        return f"EPSG:{32700 + zone}"


def run_pipeline(
    bbox: List[float],
    event_date: str,
    out_dir: str,
    config_path: str = "configs/default.yaml",
    no_cache: bool = False,
    no_quicklooks: bool = False
) -> Dict[str, Any]:
    """
    Executes full end-to-end disaster impact assessment pipeline (L0 -> L5).
    Logs start/end time, duration, peak RAM, data downloaded (MB), and S1 fallback steps.
    """
    start_wall_time = datetime.now()
    t0 = time.time()

    out_path = Path(out_dir).resolve()
    raw_dir = out_path / "raw"
    interim_dir = out_path / "interim"
    processed_dir = out_path / "processed"
    ctrl_dir = out_path / "control"
    ctrl_raw_dir = ctrl_dir / "raw" / "s1"
    ctrl_interim_dir = ctrl_dir / "interim"
    ctrl_processed_dir = ctrl_dir / "processed"

    for p in [raw_dir, interim_dir, processed_dir, ctrl_raw_dir, ctrl_interim_dir, ctrl_processed_dir]:
        p.mkdir(parents=True, exist_ok=True)

    with open(config_path, "r") as f:
        cfg = yaml.safe_load(f)

    # Determine UTM CRS
    cfg_crs = cfg.get("case_study", {}).get("utm_crs", "auto")
    if cfg_crs == "auto" or not cfg_crs:
        utm_crs = auto_utm_crs(bbox)
    else:
        utm_crs = cfg_crs

    prep_cfg = cfg.get("preprocessing", {})
    det_cfg = cfg.get("detection", {})
    dmg_cfg = cfg.get("damage_grading", {})
    rt_cfg = cfg.get("routing", {})
    perf_cfg = cfg.get("performance", {})

    max_threads = int(perf_cfg.get("max_threads", 2))
    enable_quicklooks = not no_quicklooks
    if not perf_cfg.get("enable_quicklooks", True):
        enable_quicklooks = False

    logger.info("==================================================================")
    logger.info("      DISASTER IMPACT ASSESSMENT END-TO-END PIPELINE (L0 - L5)    ")
    logger.info("==================================================================")
    logger.info(f"Target Bounding Box: {bbox}")
    logger.info(f"Event Date:          {event_date}")
    logger.info(f"Target UTM CRS:      {utm_crs}")
    logger.info(f"Output Directory:    {out_path}")
    logger.info(f"Config File:         {config_path}")

    layer_logs = {}

    # Check for pre-existing cached data in project data/ directory for this bbox/date
    data_dir = Path("data").resolve()
    if not no_cache and data_dir.exists() and (raw_dir / "s1" / "pre.tif").exists() is False:
        cached_meta = data_dir / "raw" / "s1" / "meta.json"
        if cached_meta.exists():
            try:
                with open(cached_meta) as f:
                    m = json.load(f)
                if m.get("event_date") == event_date and m.get("bbox") == bbox:
                    logger.info("Found matching cached raw and stack data in data/. Populating run directory...")
                    shutil.copytree(data_dir / "raw", raw_dir, dirs_exist_ok=True)
                    if (data_dir / "control" / "raw" / "s1").exists():
                        shutil.copytree(data_dir / "control" / "raw" / "s1", ctrl_raw_dir, dirs_exist_ok=True)
                    if (data_dir / "control" / "processed").exists():
                        shutil.copytree(data_dir / "control" / "processed", ctrl_processed_dir, dirs_exist_ok=True)
                    if (data_dir / "interim" / "s2_cache").exists():
                        shutil.copytree(data_dir / "interim" / "s2_cache", interim_dir / "s2_cache", dirs_exist_ok=True)
                    if (data_dir / "interim" / "s1_cache").exists():
                        shutil.copytree(data_dir / "interim" / "s1_cache", interim_dir / "s1_cache", dirs_exist_ok=True)
            except Exception as e:
                logger.warning(f"Could not reuse cached data: {e}")

    status_file = out_path / "status.json"
    update_status_file(status_file, "RUNNING", 0.05, 0.0, "Starting Pipeline Execution")

    # ==================================================================
    # LAYER 0: DATA INGESTION (PARALLEL: S1, DEM, OSM BBOX, OSM BUFFER, S2)
    # ==================================================================
    l0_start_time = datetime.now()
    t_l0_0 = time.time()
    s2_cache_path = interim_dir / "s2_cache"
    size_raw_before = get_dir_size_mb(raw_dir) + get_dir_size_mb(ctrl_raw_dir) + get_dir_size_mb(s2_cache_path)

    logger.info("\n>>> EXECUTING LAYER 0: DATA INGESTION (PARALLEL)")
    s1_pre_path = raw_dir / "s1" / "pre.tif"
    s1_post_path = raw_dir / "s1" / "post.tif"
    s1_meta_path = raw_dir / "s1" / "meta.json"
    dem_cands = [raw_dir / "dem" / "dem_buffered.tif", raw_dir / "dem" / "dem_glo30_buffered.tif", raw_dir / "dem" / "dem.tif"]
    dem_file = next((p for p in dem_cands if p.exists()), raw_dir / "dem" / "dem_buffered.tif")

    l0_notes = []
    l0_sources = {}

    def _task_s1():
        t0_src = time.time()
        s_before = get_dir_size_mb(raw_dir / "s1") + get_dir_size_mb(ctrl_raw_dir)
        if no_cache or not (s1_pre_path.exists() and s1_post_path.exists() and s1_meta_path.exists()):
            logger.info("Fetching Sentinel-1 RTC event and control pairs via STAC...")
            fetch_pair(bbox, event_date, str(raw_dir / "s1"), control_out_dir=str(ctrl_raw_dir), force=no_cache)
        else:
            logger.info(f"Using verified existing Sentinel-1 data in {raw_dir / 's1'}")
        dur = round(time.time() - t0_src, 2)
        s_after = get_dir_size_mb(raw_dir / "s1") + get_dir_size_mb(ctrl_raw_dir)
        l0_sources["s1"] = {"duration_s": dur, "downloaded_mb": round(max(0.0, s_after - s_before), 2)}

    def _task_dem():
        t0_src = time.time()
        s_before = get_dir_size_mb(raw_dir / "dem")
        if no_cache or not dem_file.exists():
            logger.info("Fetching Copernicus DEM GLO-30 via STAC...")
            fetch_dem(bbox, str(raw_dir / "dem"), buffer_km=prep_cfg.get("dem_buffer_km", 10.0), force=no_cache)
        else:
            logger.info(f"Using verified existing DEM in {dem_file}")
        dur = round(time.time() - t0_src, 2)
        s_after = get_dir_size_mb(raw_dir / "dem")
        l0_sources["dem"] = {"duration_s": dur, "downloaded_mb": round(max(0.0, s_after - s_before), 2)}

    def _task_osm_bbox():
        t0_src = time.time()
        s_before = get_dir_size_mb(raw_dir / "osm")
        logger.info("Fetching pre-event OSM inside bbox...")
        fetch_osm(bbox, event_date, str(raw_dir / "osm"), force=no_cache)
        dur = round(time.time() - t0_src, 2)
        s_after = get_dir_size_mb(raw_dir / "osm")
        l0_sources["osm_bbox"] = {"duration_s": dur, "downloaded_mb": round(max(0.0, s_after - s_before), 2)}

    def _task_osm_buf():
        t0_src = time.time()
        buf_osm_dir = raw_dir / "osm_buffered"
        s_before = get_dir_size_mb(buf_osm_dir)
        logger.info("Fetching pre-event buffered OSM (roads, health facilities, places)...")
        fetch_buffered_osm(
            bbox=bbox,
            buffer_km=rt_cfg.get("buffer_km", 30.0),
            event_date=event_date,
            utm_crs=utm_crs,
            out_dir=str(buf_osm_dir),
            force=no_cache
        )
        dur = round(time.time() - t0_src, 2)
        s_after = get_dir_size_mb(buf_osm_dir)
        l0_sources["osm_buffered"] = {"duration_s": dur, "downloaded_mb": round(max(0.0, s_after - s_before), 2)}

    def _task_s2():
        t0_src = time.time()
        s_before = get_dir_size_mb(s2_cache_path)
        logger.info("Fetching Sentinel-2 optical scenes...")
        s2_res = fetch_s2(
            bbox=bbox,
            event_date=event_date,
            out_dir=str(s2_cache_path),
            utm_crs=utm_crs,
            s2_pre_days=det_cfg.get("s2_pre_days", 15),
            s2_post_days=det_cfg.get("s2_post_days", 15),
            s2_post_max_days=det_cfg.get("s2_post_max_days", 45),
            s2_max_scenes=det_cfg.get("s2_max_scenes", 15),
            s2_search_timeout_s=det_cfg.get("s2_search_timeout_s", 60.0),
            s2_scene_timeout_s=det_cfg.get("s2_scene_timeout_s", 40.0),
            s2_total_budget_s=det_cfg.get("s2_total_budget_s", None),
            force=no_cache
        )
        dur = round(time.time() - t0_src, 2)
        s_after = get_dir_size_mb(s2_cache_path)
        l0_sources["s2"] = {
            "duration_s": dur,
            "downloaded_mb": round(max(0.0, s_after - s_before), 2),
            "scenes_used": s2_res.get("scenes", []),
            "scenes_skipped": s2_res.get("skipped_scenes", []),
            "budget_exceeded": s2_res.get("budget_exceeded", False)
        }

    try:
        l0_executor = concurrent.futures.ThreadPoolExecutor(max_workers=5)
        f_s1 = l0_executor.submit(_task_s1)
        f_dem = l0_executor.submit(_task_dem)
        f_osm_bbox = l0_executor.submit(_task_osm_bbox)
        f_osm_buf = l0_executor.submit(_task_osm_buf)
        f_s2 = l0_executor.submit(_task_s2)

        # 1. Wait ONLY for S1 and DEM so L1 Preprocessing can start immediately!
        f_s1.result()
        f_dem.result()
    except Exception as e:
        logger.error(f"[ERROR] Layer 0 ingestion failed: {e}")
        l0_notes.append(f"Ingestion error: {e}")
        raise e

    dem_file = next((p for p in dem_cands if p.exists()), raw_dir / "dem" / "dem_buffered.tif")
    logger.info("[PROGRESS] S1 and DEM ready! Starting L1 Preprocessing immediately...")

    # ==================================================================
    # LAYER 1: PREPROCESSING (EVENT & CONTROL IN PARALLEL)
    # ==================================================================
    l1_start_time = datetime.now()
    t_l1_0 = time.time()
    logger.info("\n>>> EXECUTING LAYER 1: PREPROCESSING (OVERLAPPED WITH S2 & OSM DOWNLOADS)")

    ctrl_pre = ctrl_raw_dir / "pre.tif"
    ctrl_post = ctrl_raw_dir / "post.tif"
    ctrl_meta = ctrl_raw_dir / "meta.json"

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as l1_pool:
        f_ev = l1_pool.submit(
            run_layer1,
            pre_path=str(s1_pre_path),
            post_path=str(s1_post_path),
            dem_path=str(dem_file),
            meta_path=str(s1_meta_path),
            out_dir=str(interim_dir),
            window_size=prep_cfg.get("filter_window_size", 5),
            drainage_threshold=prep_cfg.get("drainage_accumulation_threshold", 5000),
            look_angle_deg=prep_cfg.get("look_angle_deg", 38.0),
            orbit_heading_deg=prep_cfg.get("orbit_heading_deg", 350.0),
            dem_buffer_km=prep_cfg.get("dem_buffer_km", 10.0),
            enable_quicklooks=enable_quicklooks,
            max_threads=max_threads
        )
        if ctrl_pre.exists() and ctrl_post.exists():
            f_ctrl = l1_pool.submit(
                run_layer1,
                pre_path=str(ctrl_pre),
                post_path=str(ctrl_post),
                dem_path=str(dem_file),
                meta_path=str(ctrl_meta) if ctrl_meta.exists() else None,
                out_dir=str(ctrl_interim_dir),
                window_size=prep_cfg.get("filter_window_size", 5),
                drainage_threshold=prep_cfg.get("drainage_accumulation_threshold", 5000),
                look_angle_deg=prep_cfg.get("look_angle_deg", 38.0),
                orbit_heading_deg=prep_cfg.get("orbit_heading_deg", 350.0),
                dem_buffer_km=prep_cfg.get("dem_buffer_km", 10.0),
                enable_quicklooks=enable_quicklooks,
                max_threads=max_threads
            )
        else:
            f_ctrl = None

        l1_res = f_ev.result()
        if f_ctrl:
            f_ctrl.result()

    l1_duration_s = round(time.time() - t_l1_0, 2)
    layer_logs["L1"] = {
        "start": l1_start_time.isoformat(),
        "end": datetime.now().isoformat(),
        "duration_s": l1_duration_s,
        "peak_ram_mb": get_peak_ram_mb(),
        "current_rss_mb": get_current_rss_mb(),
        "downloaded_mb": 0.0,
        "s1_cloud_fallback": False,
        "notes": "Grid shape: " + str(l1_res.get("shape", ""))
    }
    update_status_file(status_file, "RUNNING", 0.40, time.time() - t0, "L1 Preprocessing Completed")
    logger.info(f"[PROGRESS] Step L1 (Preprocessing) finished in {l1_duration_s}s (elapsed: {round(time.time() - t0, 2)}s)")

    # Await Sentinel-2 download for Layer 2
    f_s2.result()

    # Finalize L0 metrics (raw files only, excluding L1 interim rasters)
    size_raw_after = get_dir_size_mb(raw_dir) + get_dir_size_mb(ctrl_raw_dir) + get_dir_size_mb(s2_cache_path)
    l0_downloaded_mb = round(max(0.0, size_raw_after - size_raw_before), 2)
    l0_duration_s = round(time.time() - t_l0_0, 2)
    layer_logs["L0"] = {
        "start": l0_start_time.isoformat(),
        "end": datetime.now().isoformat(),
        "duration_s": l0_duration_s,
        "peak_ram_mb": get_peak_ram_mb(),
        "current_rss_mb": get_current_rss_mb(),
        "downloaded_mb": l0_downloaded_mb,
        "s1_cloud_fallback": False,
        "sources": l0_sources,
        "notes": "; ".join(l0_notes) if l0_notes else "OK"
    }
    update_status_file(status_file, "RUNNING", 0.20, time.time() - t0, "L0 Data Ingestion Completed")
    logger.info(f"[PROGRESS] Step L0 (Data Ingestion) finished in {l0_duration_s}s (elapsed: {round(time.time() - t0, 2)}s)")
    # ==================================================================
    # LAYER 2: MULTI-SENSOR DETECTION (S2 PRIMARY + S1 SAR FALLBACK)
    # ==================================================================
    l2_start_time = datetime.now()
    t_l2_0 = time.time()
    logger.info("\n>>> EXECUTING LAYER 2: DETECTION (SENTINEL-2 + SENTINEL-1 SAR)")

    s2_cache_path = interim_dir / "s2_cache"
    s1_cache_path = interim_dir / "s1_cache"
    s1_stack_path = raw_dir / "s1_stack"

    l2_res = run_layer2(
        interim_dir=str(interim_dir),
        control_interim_dir=str(ctrl_interim_dir),
        s2_cache_dir=str(s2_cache_path),
        s1_cache_dir=str(s1_cache_path),
        s1_stack_dir=str(s1_stack_path),
        osm_waterways_path=str(raw_dir / "osm" / "osm_waterways.geojson"),
        osm_buildings_path=str(raw_dir / "osm" / "osm_buildings.geojson"),
        out_dir=str(processed_dir),
        control_out_dir=str(ctrl_processed_dir),
        false_alarm_rate_pct=det_cfg.get("false_alarm_rate_pct", 1.0),
        max_hand_corridor_m=det_cfg.get("max_hand_corridor_m", 40.0),
        stream_proximity_m=det_cfg.get("stream_proximity_m", 100.0),
        min_area_pixels=det_cfg.get("min_area_pixels", 20),
        cloud_dilation_buffer_m=det_cfg.get("cloud_dilation_buffer_m", 60.0),
        simplify_tol_m=det_cfg.get("simplify_tolerance_m", 8.0),
        reach_length_m=det_cfg.get("reach_length_m", 250.0),
        inferred_hand_percentile=det_cfg.get("inferred_hand_percentile", 90.0),
        inferred_min_observed_pixels=det_cfg.get("inferred_min_observed_pixels", 50),
        inferred_min_reach_fraction=det_cfg.get("inferred_min_reach_fraction", 0.20),
        min_abs_d_ndvi_floor=det_cfg.get("min_abs_d_ndvi_floor", -0.20),
        min_d_bsi_floor=det_cfg.get("min_d_bsi_floor", 0.18),
        min_channel_cvm_floor=det_cfg.get("min_channel_cvm_floor", 0.20),
        min_builtup_cvm_floor=det_cfg.get("min_builtup_cvm_floor", 0.15),
        building_buffer_m=det_cfg.get("building_buffer_m", 10.0),
        building_damage_proximity_m=det_cfg.get("building_damage_proximity_m", 50.0),
        intact_min_post_ndvi=det_cfg.get("intact_min_post_ndvi", 0.40),
        intact_max_abs_d_ndvi=det_cfg.get("intact_max_abs_d_ndvi", 0.20),
        min_control_clear_pixels=det_cfg.get("min_control_clear_pixels", 500),
        event_date=event_date,
        enable_quicklooks=enable_quicklooks
    )

    ev_s1_km2 = l2_res.get("areas_km2", {}).get("event_s1_affected", 0.0)
    ev_s2_km2 = l2_res.get("areas_km2", {}).get("event_s2_affected", 0.0)
    s1_used_for_clouds = bool(ev_s1_km2 > 0 or not (s2_cache_path.exists() and list(s2_cache_path.glob("*.npz"))))

    l2_duration_s = round(time.time() - t_l2_0, 2)
    layer_logs["L2"] = {
        "start": l2_start_time.isoformat(),
        "end": datetime.now().isoformat(),
        "duration_s": l2_duration_s,
        "peak_ram_mb": get_peak_ram_mb(),
        "current_rss_mb": get_current_rss_mb(),
        "downloaded_mb": 0.0,
        "s1_cloud_fallback": s1_used_for_clouds,
        "notes": f"Affected S2: {ev_s2_km2} km², S1: {ev_s1_km2} km², Inferred: {l2_res.get('areas_km2', {}).get('event_inferred_affected', 0.0)} km²"
    }

    # Progressive L2 output
    l2_summary = {
        "status": "L2_COMPLETED",
        "timestamp": datetime.now().isoformat(),
        "elapsed_seconds": round(time.time() - t0, 2),
        "duration_s": l2_duration_s,
        "areas_km2": l2_res.get("areas_km2", {}),
        "optical_evidence_note": l2_res.get("optical_evidence_note", ""),
        "outputs": {
            "hazard_classes_tif": "processed/hazard_classes.tif",
            "hazard_polygons_geojson": "processed/hazard_polygons.geojson",
            "l2_quicklook": "processed/quicklook_layer2.png"
        }
    }
    with open(processed_dir / "l2_summary.json", "w") as f:
        json.dump(l2_summary, f, indent=2)

    update_status_file(status_file, "RUNNING", 0.60, time.time() - t0, "L2 Detection Completed", outputs=l2_summary["outputs"], metrics=l2_summary["areas_km2"])
    logger.info(f"[PROGRESS] Step L2 (Multi-Sensor Detection) finished in {l2_duration_s}s (elapsed: {round(time.time() - t0, 2)}s)")

    # ==================================================================
    # LAYER 4: INFRASTRUCTURE DAMAGE GRADING
    # ==================================================================
    l4_start_time = datetime.now()
    t_l4_0 = time.time()
    logger.info("\n>>> EXECUTING LAYER 4: DAMAGE GRADING")

    # Await OSM bbox data for Layer 4
    f_osm_bbox.result()

    s2_valid_arr = np.load(interim_dir / "s2_event_valid.npy") if (interim_dir / "s2_event_valid.npy").exists() else None
    s2_vis_arr = np.load(interim_dir / "s2_post_visual.npy") if (interim_dir / "s2_post_visual.npy").exists() else None

    l4_res = run_layer4(
        osm_dir=str(raw_dir / "osm"),
        hazard_polygons_path=str(processed_dir / "hazard_polygons.geojson"),
        nodata_mask_path=str(interim_dir / "nodata_mask.tif"),
        s2_cache_dir=str(s2_cache_path),
        out_dir=str(processed_dir),
        bbox=bbox,
        utm_crs=utm_crs,
        building_overlap_pct=dmg_cfg.get("building_overlap_pct", 50.0),
        distance_damaged_m=dmg_cfg.get("distance_damaged_m", 10.0),
        distance_possibly_damaged_m=dmg_cfg.get("distance_possibly_damaged_m", 30.0),
        road_segment_length_m=dmg_cfg.get("road_segment_length_m", 100.0),
        bridge_distance_m=dmg_cfg.get("bridge_distance_m", 30.0),
        bridge_reach_radius_m=dmg_cfg.get("bridge_reach_radius_m", 100.0),
        s2_valid_mask=s2_valid_arr,
        s2_post_visual=s2_vis_arr,
        enable_quicklooks=enable_quicklooks
    )

    # 2. Control L4
    ctrl_haz_poly = ctrl_processed_dir / "hazard_polygons.geojson"
    if ctrl_haz_poly.exists():
        logger.info("Executing Layer 4 damage grading for CONTROL...")
        run_layer4(
            osm_dir=str(raw_dir / "osm"),
            hazard_polygons_path=str(ctrl_haz_poly),
            nodata_mask_path=str(interim_dir / "nodata_mask.tif"),
            s2_cache_dir=str(s2_cache_path),
            out_dir=str(ctrl_processed_dir),
            bbox=bbox,
            utm_crs=utm_crs,
            building_overlap_pct=dmg_cfg.get("building_overlap_pct", 50.0),
            distance_damaged_m=dmg_cfg.get("distance_damaged_m", 10.0),
            distance_possibly_damaged_m=dmg_cfg.get("distance_possibly_damaged_m", 30.0),
            road_segment_length_m=dmg_cfg.get("road_segment_length_m", 100.0),
            bridge_distance_m=dmg_cfg.get("bridge_distance_m", 30.0),
            bridge_reach_radius_m=dmg_cfg.get("bridge_reach_radius_m", 100.0),
            s2_valid_mask=s2_valid_arr,
            s2_post_visual=s2_vis_arr,
            enable_quicklooks=enable_quicklooks
        )

    l4_duration_s = round(time.time() - t_l4_0, 2)
    b_counts = l4_res.get("buildings", {}).get("damage_grade_counts", {})
    br_counts = l4_res.get("bridges", {}).get("damage_grade_counts", {})
    layer_logs["L4"] = {
        "start": l4_start_time.isoformat(),
        "end": datetime.now().isoformat(),
        "duration_s": l4_duration_s,
        "peak_ram_mb": get_peak_ram_mb(),
        "current_rss_mb": get_current_rss_mb(),
        "downloaded_mb": 0.0,
        "s1_cloud_fallback": False,
        "notes": f"Buildings: {b_counts}, Bridges: {br_counts}"
    }

    # Progressive L4 output
    l4_summary = {
        "status": "L4_COMPLETED",
        "timestamp": datetime.now().isoformat(),
        "elapsed_seconds": round(time.time() - t0, 2),
        "duration_s": l4_duration_s,
        "buildings": l4_res.get("buildings", {}),
        "bridges": l4_res.get("bridges", {}),
        "roads": l4_res.get("roads", {}),
        "outputs": {
            "buildings_graded_geojson": "processed/buildings_graded.geojson",
            "bridges_graded_geojson": "processed/bridges_graded.geojson",
            "roads_graded_geojson": "processed/roads_graded.geojson",
            "l4_quicklook": "processed/quicklook_l4.png"
        }
    }
    with open(processed_dir / "l4_summary.json", "w") as f:
        json.dump(l4_summary, f, indent=2)

    update_status_file(status_file, "RUNNING", 0.80, time.time() - t0, "L4 Damage Grading Completed", outputs=l4_summary["outputs"])
    logger.info(f"[PROGRESS] Step L4 (Damage Grading) finished in {l4_duration_s}s (elapsed: {round(time.time() - t0, 2)}s)")

    # ==================================================================
    # LAYER 5: ROUTING & SETTLEMENT ISOLATION
    # ==================================================================
    l5_start_time = datetime.now()
    t_l5_0 = time.time()
    # Await buffered OSM data for Layer 5
    f_osm_buf.result()
    l0_executor.shutdown()

    l5_res = run_layer5(
        config_path=config_path,
        bbox=bbox,
        utm_crs=utm_crs,
        event_roads_path=str(processed_dir / "roads_graded.geojson"),
        event_bridges_path=str(processed_dir / "bridges_graded.geojson"),
        control_roads_path=str(ctrl_processed_dir / "roads_graded.geojson"),
        control_bridges_path=str(ctrl_processed_dir / "bridges_graded.geojson"),
        buffered_osm_dir=str(raw_dir / "osm_buffered"),
        bbox_osm_dir=str(raw_dir / "osm"),
        out_dir=str(processed_dir / "routing"),
        control_out_dir=str(ctrl_processed_dir / "routing"),
        artifact_dir=str(out_path / "artifacts"),
        enable_quicklooks=enable_quicklooks
    )

    l5_duration_s = round(time.time() - t_l5_0, 2)
    cut_off_veh = l5_res.get("event_summary", {}).get("vehicle", {}).get("optimistic", {}).get("cut_off_count", 0)
    layer_logs["L5"] = {
        "start": l5_start_time.isoformat(),
        "end": datetime.now().isoformat(),
        "duration_s": l5_duration_s,
        "peak_ram_mb": get_peak_ram_mb(),
        "current_rss_mb": get_current_rss_mb(),
        "downloaded_mb": 0.0,
        "s1_cloud_fallback": False,
        "notes": f"Cut-off settlements: {cut_off_veh}"
    }

    # Progressive L5 output
    l5_summary = {
        "status": "L5_COMPLETED",
        "timestamp": datetime.now().isoformat(),
        "elapsed_seconds": round(time.time() - t0, 2),
        "duration_s": l5_duration_s,
        "cut_off_settlements": cut_off_veh,
        "outputs": {
            "settlements_geojson": "processed/routing/settlements.geojson",
            "repair_priority_json": "processed/routing/repair_priority.json",
            "repair_packages_json": "processed/routing/repair_packages.json",
            "l5_quicklook": "processed/routing/quicklook_l5.png"
        }
    }
    with open(processed_dir / "routing" / "l5_summary.json", "w") as f:
        json.dump(l5_summary, f, indent=2)

    logger.info(f"[PROGRESS] Step L5 (Disaster Routing & Isolation) finished in {l5_duration_s}s (elapsed: {round(time.time() - t0, 2)}s)")

    total_duration_s = round(time.time() - t0, 2)
    peak_ram_overall = get_peak_ram_mb()

    # Determine sensors used
    sensors_used = ["Sentinel-1 RTC SAR", "Copernicus DEM-30", "OpenStreetMap"]
    if s2_cache_path.exists() and len(list(s2_cache_path.glob("*.npz"))) > 0:
        sensors_used.insert(0, "Sentinel-2 MSI Optical")
    s2_scenes_skipped = l0_sources.get("s2", {}).get("scenes_skipped", [])
    overall_status = "DEGRADED" if s2_scenes_skipped else "COMPLETED"

    summary_payload = {
        "status": overall_status,
        "bbox": bbox,
        "event_date": event_date,
        "utm_crs": utm_crs,
        "total_duration_seconds": total_duration_s,
        "peak_ram_mb": peak_ram_overall,
        "swap_used_mb": get_swap_used_mb(),
        "sensors_used": sensors_used,
        "optical_evidence_note": l2_res.get("optical_evidence_note", ""),
        "s2_scenes_used": l0_sources.get("s2", {}).get("scenes_used", []),
        "s2_scenes_skipped": s2_scenes_skipped,
        "l0_sources": l0_sources,
        "metrics": {
            "affected_km2_observed": l2_res.get("areas_km2", {}).get("event_total_affected", 0.0),
            "affected_km2_s2": l2_res.get("areas_km2", {}).get("event_s2_affected", 0.0),
            "affected_km2_s1": l2_res.get("areas_km2", {}).get("event_s1_affected", 0.0),
            "affected_km2_inferred": l2_res.get("areas_km2", {}).get("event_inferred_affected", 0.0),
            "buildings_affected_total": (
                b_counts.get("Destroyed", 0) + b_counts.get("Damaged", 0) + b_counts.get("Possibly damaged", 0)
            ),
            "buildings_destroyed": b_counts.get("Destroyed", 0),
            "buildings_damaged": b_counts.get("Damaged", 0),
            "buildings_possibly_damaged": b_counts.get("Possibly damaged", 0),
            "bridges_affected_total": (
                br_counts.get("Destroyed", 0) + br_counts.get("Possibly damaged", 0)
            ),
            "bridges_destroyed": br_counts.get("Destroyed", 0),
            "bridges_possibly_damaged": br_counts.get("Possibly damaged", 0),
            "cut_off_settlements": cut_off_veh
        },
        "layer_performance": layer_logs,
        "outputs": {
            "hazard_classes_tif": "processed/hazard_classes.tif",
            "hazard_polygons_geojson": "processed/hazard_polygons.geojson",
            "l2_quicklook": "processed/quicklook_layer2.png",
            "buildings_graded_geojson": "processed/buildings_graded.geojson",
            "bridges_graded_geojson": "processed/bridges_graded.geojson",
            "roads_graded_geojson": "processed/roads_graded.geojson",
            "l4_quicklook": "processed/quicklook_l4.png",
            "settlements_geojson": "processed/routing/settlements.geojson",
            "repair_priority_json": "processed/routing/repair_priority.json",
            "repair_packages_json": "processed/routing/repair_packages.json",
            "l5_quicklook": "processed/routing/quicklook_l5.png"
        }
    }

    summary_file = out_path / "run_summary.json"
    with open(summary_file, "w") as f:
        json.dump(summary_payload, f, indent=2)

    update_status_file(status_file, overall_status, 1.0, total_duration_s, f"Pipeline {overall_status}", outputs=summary_payload["outputs"], metrics=summary_payload["metrics"])
    logger.info(f"[PROGRESS] Pipeline {overall_status} in {total_duration_s}s")

    logger.info("\n==================================================================")
    logger.info("                  PIPELINE EXECUTION COMPLETED                     ")
    logger.info("==================================================================")
    logger.info(f"Total Wall Time:  {total_duration_s:.1f}s")
    logger.info(f"Peak RAM Usage:   {peak_ram_overall:.1f} MB")
    logger.info(f"Sensors Used:     {', '.join(sensors_used)}")
    if summary_payload.get("optical_evidence_note"):
        logger.info(f"Optical Evidence: {summary_payload['optical_evidence_note']}")
    logger.info(f"Affected Area:    Observed={summary_payload['metrics']['affected_km2_observed']} km², Inferred={summary_payload['metrics']['affected_km2_inferred']} km²")
    logger.info(f"Infrastructure:   Buildings={summary_payload['metrics']['buildings_affected_total']}, Bridges={summary_payload['metrics']['bridges_affected_total']}")
    logger.info(f"Cut-off Settle.:  {cut_off_veh}")
    logger.info(f"Run Summary File: {summary_file}")
    logger.info("==================================================================\n")

    return summary_payload


def main():
    parser = argparse.ArgumentParser(description="End-to-end Disaster Impact Assessment Pipeline (L0-L5)")
    parser.add_argument("--bbox", type=float, nargs=4, required=True, help="W S E N (bounding box in WGS84)")
    parser.add_argument("--event-date", type=str, required=True, help="YYYY-MM-DD (event date)")
    parser.add_argument("--out-dir", type=str, required=True, help="Output directory path")
    parser.add_argument("--config", type=str, default="configs/default.yaml", help="Path to default config yaml")
    parser.add_argument("--no-cache", action="store_true", help="Disable copying pre-existing cache from data/")
    parser.add_argument("--no-quicklooks", action="store_true", help="Disable rendering quicklook visualization plots")

    args = parser.parse_args()
    run_pipeline(
        bbox=args.bbox,
        event_date=args.event_date,
        out_dir=args.out_dir,
        config_path=args.config,
        no_cache=args.no_cache,
        no_quicklooks=args.no_quicklooks
    )


if __name__ == "__main__":
    main()
