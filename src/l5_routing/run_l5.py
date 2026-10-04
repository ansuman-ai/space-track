"""
Layer 5 Disaster Routing and Settlement Isolation Pipeline Orchestrator.
Inputs:
- OSM data in buffered area (30 km buffer)
- Layer 4 damage grading results (EVENT and CONTROL)
- Target health facility destinations
Outputs:
- settlements.geojson
- cutoff_summary.json
- quicklook_l5.png (Overview map)
- zoom_cutoff_1.png, zoom_cutoff_2.png, zoom_cutoff_3.png (Zoom maps for top 3 cut-off settlements)
- CONTROL validation execution (asserts 0 cut-offs)
"""

import os
os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")
import json
import shutil
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
import yaml
import numpy as np
import geopandas as gpd
import rasterio

from .settlements import extract_settlements
from .destinations import extract_destinations
from .network import build_routing_networks
from .connectivity import evaluate_network_connectivity
from .quicklook import render_l5_overview, render_cutoff_zoom

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("layer5_routing")


def run_layer5(
    config_path: str = "configs/trishuli.yaml",
    event_roads_path: str = "data/processed/roads_graded.geojson",
    event_bridges_path: str = "data/processed/bridges_graded.geojson",
    control_roads_path: str = "data/control/processed/roads_graded.geojson",
    control_bridges_path: str = "data/control/processed/bridges_graded.geojson",
    buffered_osm_dir: str = "data/raw/osm_buffered",
    bbox_osm_dir: str = "data/raw/osm",
    out_dir: str = "data/processed/routing",
    control_out_dir: str = "data/control/processed/routing",
    artifact_dir: str = "/home/zeus/.gemini/antigravity/brain/52dd5215-6165-4f39-8912-cfce41bfdff1"
) -> Dict[str, Any]:
    """
    Executes complete Layer 5 pipeline for EVENT and verifies CONTROL.
    """
    with open(config_path, "r") as f:
        cfg = yaml.safe_load(f)

    cs = cfg.get("case_study", cfg.get("spatial", {}))
    bbox = cs["bbox"]
    utm_crs = cs.get("utm_crs", "EPSG:32645")
    r_cfg = cfg.get("routing", {})
    max_snap_m = r_cfg.get("max_snap_distance_m", 500.0)
    dbscan_eps = r_cfg.get("dbscan_eps_m", 65.0)
    dbscan_min_samples = r_cfg.get("dbscan_min_samples", 5)
    vehicle_hwys = r_cfg.get("vehicle_highways")
    walking_extra = r_cfg.get("walking_highways_extra")

    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    ctrl_out_path = Path(control_out_dir)
    ctrl_out_path.mkdir(parents=True, exist_ok=True)

    logger.info("=== LAYER 5: DISASTER ROUTING AND SETTLEMENT ISOLATION ===")

    # 1. Settlements Extraction
    logger.info("Extracting settlements (place nodes + DBSCAN building clusters)...")
    places_path = os.path.join(buffered_osm_dir, "osm_places.geojson")
    buildings_path = os.path.join(bbox_osm_dir, "osm_buildings.geojson")
    settlements_gdf = extract_settlements(
        places_path=places_path,
        buildings_path=buildings_path,
        bbox=bbox,
        eps_m=dbscan_eps,
        min_samples=dbscan_min_samples,
        utm_crs=utm_crs
    )
    logger.info(f"Identified {len(settlements_gdf)} settlements in study area.")

    # 2. Destinations Extraction
    logger.info("Extracting target destinations (health facilities)...")
    hospitals_path = os.path.join(buffered_osm_dir, "osm_hospitals.geojson")
    destinations_gdf = extract_destinations(
        hospitals_path=hospitals_path,
        places_path=places_path,
        utm_crs=utm_crs
    )
    logger.info(f"Loaded {len(destinations_gdf)} destinations.")

    # 3. Build EVENT Networks
    logger.info("Building topological routing networks for EVENT...")
    roads_buffered_path = os.path.join(buffered_osm_dir, "osm_roads.geojson")
    event_net = build_routing_networks(
        roads_path=roads_buffered_path,
        hazard_roads_path=event_roads_path,
        hazard_bridges_path=event_bridges_path,
        bbox=bbox,
        vehicle_highways=vehicle_hwys,
        walking_highways_extra=walking_extra,
        utm_crs=utm_crs
    )

    # 4. Evaluate EVENT Connectivity
    logger.info("Evaluating connectivity on VEHICLE network...")
    v_res = evaluate_network_connectivity(
        G=event_net["G_vehicle"],
        settlements_gdf=settlements_gdf,
        destinations_gdf=destinations_gdf,
        network_name="vehicle",
        max_snap_distance_m=max_snap_m
    )

    logger.info("Evaluating connectivity on WALKING network...")
    w_res = evaluate_network_connectivity(
        G=event_net["G_walking"],
        settlements_gdf=settlements_gdf,
        destinations_gdf=destinations_gdf,
        network_name="walking",
        max_snap_distance_m=max_snap_m
    )

    # Map results to settlements GeoDataFrame
    v_dict = {r["settlement_id"]: r for r in v_res["settlement_details"]}
    w_dict = {r["settlement_id"]: r for r in w_res["settlement_details"]}

    settlements_out = settlements_gdf.copy()
    settlements_out["vehicle_status_opt"] = [v_dict[sid]["status_optimistic"] for sid in settlements_out["settlement_id"]]
    settlements_out["vehicle_status_pess"] = [v_dict[sid]["status_pessimistic"] for sid in settlements_out["settlement_id"]]
    settlements_out["vehicle_pre_dist_km"] = [v_dict[sid]["pre_distance_km"] for sid in settlements_out["settlement_id"]]
    settlements_out["vehicle_post_dist_opt_km"] = [v_dict[sid]["post_distance_opt_km"] for sid in settlements_out["settlement_id"]]
    settlements_out["vehicle_detour_opt_km"] = [v_dict[sid]["detour_opt_km"] for sid in settlements_out["settlement_id"]]
    settlements_out["vehicle_broken_element_opt"] = [
        str(v_dict[sid]["broken_element_opt"]["osm_id"]) if v_dict[sid]["broken_element_opt"] else None
        for sid in settlements_out["settlement_id"]
    ]

    settlements_out["walking_status_opt"] = [w_dict[sid]["status_optimistic"] for sid in settlements_out["settlement_id"]]
    settlements_out["walking_status_pess"] = [w_dict[sid]["status_pessimistic"] for sid in settlements_out["settlement_id"]]
    settlements_out["walking_pre_dist_km"] = [w_dict[sid]["pre_distance_km"] for sid in settlements_out["settlement_id"]]
    settlements_out["walking_post_dist_opt_km"] = [w_dict[sid]["post_distance_opt_km"] for sid in settlements_out["settlement_id"]]
    settlements_out["walking_detour_opt_km"] = [w_dict[sid]["detour_opt_km"] for sid in settlements_out["settlement_id"]]
    settlements_out["walking_broken_element_opt"] = [
        str(w_dict[sid]["broken_element_opt"]["osm_id"]) if w_dict[sid]["broken_element_opt"] else None
        for sid in settlements_out["settlement_id"]
    ]

    # Save settlements.geojson in EPSG:4326 for standard GIS interoperability
    settle_geojson_path = out_path / "settlements.geojson"
    settlements_out.to_crs("EPSG:4326").to_file(settle_geojson_path, driver="GeoJSON")
    logger.info(f"Saved settlements to {settle_geojson_path}")

    # Build cutoff_summary.json
    cutoff_summary = {
        "metadata": {
            "event": "Trishuli / Syabru Besi Flood-Landslide 2026",
            "bbox": bbox,
            "crs": utm_crs,
            "total_settlements": len(settlements_gdf),
            "destinations_count": len(destinations_gdf)
        },
        "vehicle": {
            "total_settlements": len(settlements_gdf),
            "no_network_access": sum(1 for r in v_res["settlement_details"] if r["status_optimistic"] == "no_network_access"),
            "optimistic": {
                "cut_off_count": v_res["optimistic"]["cut_off_count"],
                "connected_count": v_res["optimistic"]["connected_count"],
                "cut_off_settlements": [
                    {k: v for k, v in item.items() if k != "pre_path"}
                    for item in v_res["optimistic"]["cut_off_settlements"]
                ]
            },
            "pessimistic": {
                "cut_off_count": v_res["pessimistic"]["cut_off_count"],
                "connected_count": v_res["pessimistic"]["connected_count"],
                "cut_off_settlements": [
                    {k: v for k, v in item.items() if k != "pre_path"}
                    for item in v_res["pessimistic"]["cut_off_settlements"]
                ]
            }
        },
        "walking": {
            "total_settlements": len(settlements_gdf),
            "no_network_access": sum(1 for r in w_res["settlement_details"] if r["status_optimistic"] == "no_network_access"),
            "optimistic": {
                "cut_off_count": w_res["optimistic"]["cut_off_count"],
                "connected_count": w_res["optimistic"]["connected_count"],
                "cut_off_settlements": [
                    {k: v for k, v in item.items() if k != "pre_path"}
                    for item in w_res["optimistic"]["cut_off_settlements"]
                ]
            },
            "pessimistic": {
                "cut_off_count": w_res["pessimistic"]["cut_off_count"],
                "connected_count": w_res["pessimistic"]["connected_count"],
                "cut_off_settlements": [
                    {k: v for k, v in item.items() if k != "pre_path"}
                    for item in w_res["pessimistic"]["cut_off_settlements"]
                ]
            }
        }
    }

    summary_json_path = out_path / "cutoff_summary.json"
    with open(summary_json_path, "w", encoding="utf-8") as f:
        json.dump(cutoff_summary, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved cutoff summary to {summary_json_path}")

    # 5. Visualizations
    logger.info("Loading S2 optical composite for visualizations...")
    s2_cache_npz = Path("data/interim/s2_cache/post_119_S2B_MSIL2A_20260827T045659_R11.npz")
    s2_vis = None
    trans = None
    ref_tif = Path("data/processed/hazard_classes.tif")
    if ref_tif.exists():
        with rasterio.open(ref_tif) as src:
            trans = src.transform

    if s2_cache_npz.exists():
        d = np.load(s2_cache_npz)
        if "visual" in d:
            s2_vis = d["visual"]

    # Overview Quicklook
    overview_png = str(out_path / "quicklook_l5.png")
    logger.info(f"Rendering Layer 5 overview quicklook to {overview_png}...")
    render_l5_overview(
        settlements_gdf=settlements_out,
        destinations_gdf=destinations_gdf,
        roads_graded_path=event_roads_path,
        bridges_graded_path=event_bridges_path,
        output_png_path=overview_png,
        s2_post_visual=s2_vis,
        transform_matrix=trans,
        bbox=bbox,
        utm_crs=utm_crs
    )

    # 3 Zoom Plots for largest cut-off settlements
    top_3_cutoff = sorted(v_res["optimistic"]["cut_off_settlements"], key=lambda x: x["building_count"], reverse=True)[:3]
    all_roads_gdf = gpd.read_file(roads_buffered_path).to_crs(utm_crs)

    zoom_png_paths = []
    for rank_idx, s_cut in enumerate(top_3_cutoff, start=1):
        zoom_png = str(out_path / f"zoom_cutoff_{rank_idx}.png")
        logger.info(f"Rendering Zoom plot #{rank_idx} for {s_cut['name']} ({s_cut['building_count']} buildings)...")
        render_cutoff_zoom(
            settlement_dict=s_cut,
            rank=rank_idx,
            output_png_path=zoom_png,
            s2_post_visual=s2_vis,
            transform_matrix=trans,
            all_roads_gdf=all_roads_gdf,
            utm_crs=utm_crs
        )
        zoom_png_paths.append(zoom_png)

    # 6. CONTROL RUN CHECK
    logger.info("=== RUNNING CONTROL RUN VALIDATION CHECK ===")
    ctrl_net = build_routing_networks(
        roads_path=roads_buffered_path,
        hazard_roads_path=control_roads_path,
        hazard_bridges_path=control_bridges_path,
        bbox=bbox,
        vehicle_highways=vehicle_hwys,
        walking_highways_extra=walking_extra,
        utm_crs=utm_crs
    )
    ctrl_v_res = evaluate_network_connectivity(
        G=ctrl_net["G_vehicle"],
        settlements_gdf=settlements_gdf,
        destinations_gdf=destinations_gdf,
        network_name="vehicle_control",
        max_snap_distance_m=max_snap_m
    )
    ctrl_w_res = evaluate_network_connectivity(
        G=ctrl_net["G_walking"],
        settlements_gdf=settlements_gdf,
        destinations_gdf=destinations_gdf,
        network_name="walking_control",
        max_snap_distance_m=max_snap_m
    )

    ctrl_v_cutoff = ctrl_v_res["optimistic"]["cut_off_count"]
    ctrl_w_cutoff = ctrl_w_res["optimistic"]["cut_off_count"]
    logger.info(f"CONTROL Check: Vehicle cut-off = {ctrl_v_cutoff}, Walking cut-off = {ctrl_w_cutoff}")

    ctrl_summary = {
        "vehicle_cutoff_count": ctrl_v_cutoff,
        "walking_cutoff_count": ctrl_w_cutoff,
        "vehicle_connected_count": ctrl_v_res["optimistic"]["connected_count"],
        "walking_connected_count": ctrl_w_res["optimistic"]["connected_count"]
    }
    with open(ctrl_out_path / "cutoff_summary_control.json", "w") as f:
        json.dump(ctrl_summary, f, indent=2)

    # Assert cut-offs must be exactly 0
    assert ctrl_v_cutoff == 0, f"CONTROL vehicle cut-offs must be 0, got {ctrl_v_cutoff}"
    assert ctrl_w_cutoff == 0, f"CONTROL walking cut-offs must be 0, got {ctrl_w_cutoff}"

    # Copy artifacts to artifact dir
    if os.path.exists(artifact_dir):
        for p in [overview_png] + zoom_png_paths:
            if os.path.exists(p):
                shutil.copy(p, os.path.join(artifact_dir, os.path.basename(p)))

    return {
        "event_summary": cutoff_summary,
        "control_summary": ctrl_summary,
        "overview_png": overview_png,
        "zoom_png_paths": zoom_png_paths
    }


if __name__ == "__main__":
    run_layer5()
