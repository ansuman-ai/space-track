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

# Pipeline modules
from src.l0_ingestion.run_l0 import run_layer0
from src.l0_ingestion.fetch_osm import fetch_osm
from src.l0_ingestion.fetch_dem import fetch_dem
from src.l0_ingestion.fetch_s1 import fetch_pair
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


def get_peak_ram_mb() -> float:
    """Returns peak resident set size (RSS) in MB."""
    # ru_maxrss is in kilobytes on Linux
    return round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0, 2)


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
    config_path: str = "configs/default.yaml"
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
    if data_dir.exists() and (raw_dir / "s1" / "pre.tif").exists() is False:
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

    # ==================================================================
    # LAYER 0: DATA INGESTION
    # ==================================================================
    l0_start_time = datetime.now()
    t_l0_0 = time.time()
    size_raw_before = get_dir_size_mb(raw_dir) + get_dir_size_mb(ctrl_dir)

    logger.info("\n>>> EXECUTING LAYER 0: DATA INGESTION")
    s1_pre_path = raw_dir / "s1" / "pre.tif"
    s1_post_path = raw_dir / "s1" / "post.tif"
    s1_meta_path = raw_dir / "s1" / "meta.json"
    dem_cands = [raw_dir / "dem" / "dem_buffered.tif", raw_dir / "dem" / "dem_glo30_buffered.tif", raw_dir / "dem" / "dem.tif"]
    dem_file = next((p for p in dem_cands if p.exists()), raw_dir / "dem" / "dem_buffered.tif")

    l0_notes = []
    try:
        # Step 0a: Sentinel-1 RTC event & control pair
        if not (s1_pre_path.exists() and s1_post_path.exists() and s1_meta_path.exists()):
            logger.info("Fetching Sentinel-1 RTC event and control pairs via STAC...")
            fetch_pair(bbox, event_date, str(raw_dir / "s1"), control_out_dir=str(ctrl_raw_dir))
        else:
            logger.info(f"Using verified existing Sentinel-1 data in {raw_dir / 's1'}")

        # Step 0b: Copernicus DEM GLO-30
        if not dem_file.exists():
            logger.info("Fetching Copernicus DEM GLO-30 via STAC...")
            fetch_dem(bbox, str(raw_dir / "dem"), buffer_km=prep_cfg.get("dem_buffer_km", 10.0))
        else:
            logger.info(f"Using verified existing DEM in {dem_file}")

        # Step 0c: Pre-event OSM inside bbox
        fetch_osm(bbox, event_date, str(raw_dir / "osm"))

        # Step 0d: Pre-event buffered OSM for L5 routing
        buf_osm_dir = raw_dir / "osm_buffered"
        fetch_buffered_osm(
            bbox=bbox,
            buffer_km=rt_cfg.get("buffer_km", 30.0),
            event_date=event_date,
            utm_crs=utm_crs,
            out_dir=str(buf_osm_dir)
        )
    except Exception as e:
        logger.error(f"[ERROR] Layer 0 ingestion failed: {e}")
        l0_notes.append(f"Ingestion error: {e}")
        raise e

    size_raw_after = get_dir_size_mb(raw_dir) + get_dir_size_mb(ctrl_dir)
    l0_downloaded_mb = round(max(0.0, size_raw_after - size_raw_before), 2)
    l0_duration_s = round(time.time() - t_l0_0, 2)
    layer_logs["L0"] = {
        "start": l0_start_time.isoformat(),
        "end": datetime.now().isoformat(),
        "duration_s": l0_duration_s,
        "peak_ram_mb": get_peak_ram_mb(),
        "downloaded_mb": l0_downloaded_mb,
        "s1_cloud_fallback": False,
        "notes": "; ".join(l0_notes) if l0_notes else "OK"
    }

    # ==================================================================
    # LAYER 1: PREPROCESSING (EVENT & CONTROL)
    # ==================================================================
    l1_start_time = datetime.now()
    t_l1_0 = time.time()
    logger.info("\n>>> EXECUTING LAYER 1: PREPROCESSING (EVENT & CONTROL)")

    # 1. Event L1
    l1_res = run_layer1(
        pre_path=str(s1_pre_path),
        post_path=str(s1_post_path),
        dem_path=str(dem_file),
        meta_path=str(s1_meta_path),
        out_dir=str(interim_dir),
        window_size=prep_cfg.get("filter_window_size", 5),
        drainage_threshold=prep_cfg.get("drainage_accumulation_threshold", 1000),
        look_angle_deg=prep_cfg.get("look_angle_deg", 38.0),
        orbit_heading_deg=prep_cfg.get("orbit_heading_deg", 350.0),
        dem_buffer_km=prep_cfg.get("dem_buffer_km", 10.0)
    )

    # 2. Control L1
    ctrl_pre = ctrl_raw_dir / "pre.tif"
    ctrl_post = ctrl_raw_dir / "post.tif"
    ctrl_meta = ctrl_raw_dir / "meta.json"
    if ctrl_pre.exists() and ctrl_post.exists():
        run_layer1(
            pre_path=str(ctrl_pre),
            post_path=str(ctrl_post),
            dem_path=str(dem_file),
            meta_path=str(ctrl_meta) if ctrl_meta.exists() else None,
            out_dir=str(ctrl_interim_dir),
            window_size=prep_cfg.get("filter_window_size", 5),
            drainage_threshold=prep_cfg.get("drainage_accumulation_threshold", 1000),
            look_angle_deg=prep_cfg.get("look_angle_deg", 38.0),
            orbit_heading_deg=prep_cfg.get("orbit_heading_deg", 350.0),
            dem_buffer_km=prep_cfg.get("dem_buffer_km", 10.0)
        )
    else:
        logger.warning(f"[WARNING] Missing Sentinel-1 control pair in {ctrl_raw_dir}. Continuing without separate control L1.")

    l1_duration_s = round(time.time() - t_l1_0, 2)
    layer_logs["L1"] = {
        "start": l1_start_time.isoformat(),
        "end": datetime.now().isoformat(),
        "duration_s": l1_duration_s,
        "peak_ram_mb": get_peak_ram_mb(),
        "downloaded_mb": 0.0,
        "s1_cloud_fallback": False,
        "notes": "Grid shape: " + str(l1_res.get("shape", ""))
    }

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
        event_date=event_date
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
        "downloaded_mb": 0.0,
        "s1_cloud_fallback": s1_used_for_clouds,
        "notes": f"Affected S2: {ev_s2_km2} km², S1: {ev_s1_km2} km², Inferred: {l2_res.get('areas_km2', {}).get('event_inferred_affected', 0.0)} km²"
    }

    # ==================================================================
    # LAYER 4: INFRASTRUCTURE DAMAGE GRADING
    # ==================================================================
    l4_start_time = datetime.now()
    t_l4_0 = time.time()
    logger.info("\n>>> EXECUTING LAYER 4: DAMAGE GRADING")

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
        bridge_reach_radius_m=dmg_cfg.get("bridge_reach_radius_m", 100.0)
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
            bridge_reach_radius_m=dmg_cfg.get("bridge_reach_radius_m", 100.0)
        )

    l4_duration_s = round(time.time() - t_l4_0, 2)
    b_counts = l4_res.get("buildings", {}).get("damage_grade_counts", {})
    br_counts = l4_res.get("bridges", {}).get("damage_grade_counts", {})
    layer_logs["L4"] = {
        "start": l4_start_time.isoformat(),
        "end": datetime.now().isoformat(),
        "duration_s": l4_duration_s,
        "peak_ram_mb": get_peak_ram_mb(),
        "downloaded_mb": 0.0,
        "s1_cloud_fallback": False,
        "notes": f"Buildings: {b_counts}, Bridges: {br_counts}"
    }

    # ==================================================================
    # LAYER 5: ROUTING & SETTLEMENT ISOLATION
    # ==================================================================
    l5_start_time = datetime.now()
    t_l5_0 = time.time()
    logger.info("\n>>> EXECUTING LAYER 5: ROUTING & SETTLEMENT ISOLATION")

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
        artifact_dir=str(out_path / "artifacts")
    )

    l5_duration_s = round(time.time() - t_l5_0, 2)
    cut_off_veh = l5_res.get("event_summary", {}).get("vehicle", {}).get("optimistic", {}).get("cut_off_count", 0)
    layer_logs["L5"] = {
        "start": l5_start_time.isoformat(),
        "end": datetime.now().isoformat(),
        "duration_s": l5_duration_s,
        "peak_ram_mb": get_peak_ram_mb(),
        "downloaded_mb": 0.0,
        "s1_cloud_fallback": False,
        "notes": f"Cut-off settlements: {cut_off_veh}"
    }

    total_duration_s = round(time.time() - t0, 2)
    peak_ram_overall = get_peak_ram_mb()

    # Determine sensors used
    sensors_used = ["Sentinel-1 RTC SAR", "Copernicus DEM-30", "OpenStreetMap"]
    if s2_cache_path.exists() and len(list(s2_cache_path.glob("*.npz"))) > 0:
        sensors_used.insert(0, "Sentinel-2 MSI Optical")

    summary_payload = {
        "status": "COMPLETED",
        "bbox": bbox,
        "event_date": event_date,
        "utm_crs": utm_crs,
        "total_duration_seconds": total_duration_s,
        "peak_ram_mb": peak_ram_overall,
        "sensors_used": sensors_used,
        "optical_evidence_note": l2_res.get("optical_evidence_note", ""),
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
            "hazard_classes_tif": str(processed_dir / "hazard_classes.tif"),
            "hazard_polygons_geojson": str(processed_dir / "hazard_polygons.geojson"),
            "l2_quicklook": str(processed_dir / "quicklook_layer2.png"),
            "buildings_graded_geojson": str(processed_dir / "buildings_graded.geojson"),
            "bridges_graded_geojson": str(processed_dir / "bridges_graded.geojson"),
            "roads_graded_geojson": str(processed_dir / "roads_graded.geojson"),
            "l4_quicklook": str(processed_dir / "quicklook_l4.png"),
            "settlements_geojson": str(processed_dir / "routing" / "settlements.geojson"),
            "repair_priority_json": str(processed_dir / "routing" / "repair_priority.json"),
            "repair_packages_json": str(processed_dir / "routing" / "repair_packages.json"),
            "l5_quicklook": str(processed_dir / "routing" / "quicklook_l5.png")
        }
    }

    summary_file = out_path / "run_summary.json"
    with open(summary_file, "w") as f:
        json.dump(summary_payload, f, indent=2)

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

    args = parser.parse_args()
    run_pipeline(
        bbox=args.bbox,
        event_date=args.event_date,
        out_dir=args.out_dir,
        config_path=args.config
    )


if __name__ == "__main__":
    main()
