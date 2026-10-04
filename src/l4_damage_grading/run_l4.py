"""
Layer 4 Damage Grading Pipeline Orchestrator.
Inputs:
- Pre-event OSM: data/raw/osm (buildings, roads, bridges, hospitals)
- Layer 2 Hazard Polygons: data/processed/hazard_polygons.geojson (Class 2: Observed, Class 3: Inferred)
Outputs:
- data/processed/buildings_graded.geojson
- data/processed/roads_graded.geojson
- data/processed/bridges_graded.geojson
- data/processed/damage_summary.json
- data/processed/quicklook_l4.png
"""

import os
import json
import logging
import argparse
from pathlib import Path
from typing import Dict, Any, List, Optional
import yaml
import numpy as np
import geopandas as gpd
import rasterio

from .coverage import compute_osm_coverage
from .grading import grade_buildings, grade_roads, grade_bridges
from .quicklook import render_l4_quicklook

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("layer4_damage_grading")


def run_layer4(
    osm_dir: str = "data/raw/osm",
    hazard_polygons_path: str = "data/processed/hazard_polygons.geojson",
    nodata_mask_path: str = "data/interim/nodata_mask.tif",
    s2_cache_dir: str = "data/interim/s2_cache",
    out_dir: str = "data/processed",
    bbox: Optional[List[float]] = None,
    utm_crs: str = "EPSG:32645",
    building_overlap_pct: float = 50.0,
    distance_damaged_m: float = 10.0,
    distance_possibly_damaged_m: float = 30.0,
    road_segment_length_m: float = 100.0,
    bridge_distance_m: float = 30.0,
    bridge_reach_radius_m: float = 100.0
) -> Dict[str, Any]:

    """
    Executes complete Layer 4 critical infrastructure damage grading workflow.
    """
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    osm_path = Path(osm_dir)

    logger.info("=== LAYER 4: CRITICAL INFRASTRUCTURE DAMAGE GRADING ===")

    # 1. OSM Coverage
    logger.info("Computing pre-event OSM infrastructure coverage in bbox...")
    coverage = compute_osm_coverage(osm_dir=osm_dir, bbox=bbox, utm_crs=utm_crs)
    print("\n--- 1. OSM PRE-EVENT COVERAGE IN BBOX ---")
    print(f"  Buildings:  {coverage['buildings_count']}")
    print(f"  Bridges:    {coverage['bridges_count']}")
    print(f"  Hospitals:  {coverage['hospitals_count']}")
    print(f"  Road Total: {coverage['road_km_total']} km (diagonal) / {coverage['road_perimeter_km_total']} km (perimeter)")
    print(f"  Road km by Type (diagonal): {coverage['road_km_by_type']}")

    # 2. Load Layer 2 Hazard Polygons
    logger.info(f"Loading Layer 2 hazard polygons from {hazard_polygons_path}...")
    if not os.path.exists(hazard_polygons_path):
        raise FileNotFoundError(f"Missing hazard polygons file: {hazard_polygons_path}")

    hazard_gdf = gpd.read_file(hazard_polygons_path)
    c2_count = len(hazard_gdf[hazard_gdf["class"] == 2])
    c3_count = len(hazard_gdf[hazard_gdf["class"] == 3])
    logger.info(f"Loaded hazard polygons: {c2_count} Class 2 (Observed), {c3_count} Class 3 (Inferred)")

    # 3. Load Optical Validity / Cloud / NoData Mask
    logger.info("Preparing cloud and nodata raster validity mask...")
    with rasterio.open(nodata_mask_path) as src:
        nodata = src.read(1)
        trans = src.transform
        h, w = nodata.shape
        dx = abs(trans.a)

    # Cloud mask from S2 composite
    try:
        from ..l2_detection.s2_composite import prepare_s2_event_and_control_composites
        s2_data = prepare_s2_event_and_control_composites(s2_cache_dir, dilation_buffer_m=60.0, pixel_size_m=dx)
        s2_valid = s2_data["s2_event_valid"]
        s2_post_visual = s2_data["post_composite"]["vis"]
    except Exception as e:
        logger.warning(f"Could not load S2 composite cache: {e}. Falling back to default validity.")
        s2_valid = np.ones((h, w), dtype=bool)
        s2_post_visual = np.zeros((3, h, w), dtype=np.uint8)

    cloud_or_nodata = (~s2_valid) | (nodata == 1)
    inv_trans = ~trans

    # 4. Grade Buildings
    logger.info("Grading building damage...")
    b_file = osm_path / "osm_buildings.geojson"
    if b_file.exists():
        raw_b = gpd.read_file(b_file)
        b_graded = grade_buildings(
            buildings_gdf=raw_b,
            hazard_gdf=hazard_gdf,
            cloud_nodata_mask=cloud_or_nodata,
            inv_transform=inv_trans,
            utm_crs=utm_crs,
            building_overlap_pct=building_overlap_pct,
            distance_damaged_m=distance_damaged_m,
            distance_possibly_damaged_m=distance_possibly_damaged_m
        )
    else:
        b_graded = gpd.GeoDataFrame([], crs="EPSG:4326")

    b_out_file = str(out_path / "buildings_graded.geojson")
    b_graded.to_file(b_out_file, driver="GeoJSON")
    b_counts = b_graded["damage_grade"].value_counts().to_dict() if len(b_graded) > 0 else {}
    b_ev_counts = b_graded["evidence"].value_counts().to_dict() if len(b_graded) > 0 else {}

    # 5. Grade Roads
    logger.info("Grading road network segments...")
    r_file = osm_path / "osm_roads.geojson"
    if r_file.exists():
        raw_r = gpd.read_file(r_file)
        r_graded = grade_roads(
            roads_gdf=raw_r,
            hazard_gdf=hazard_gdf,
            cloud_nodata_mask=cloud_or_nodata,
            inv_transform=inv_trans,
            utm_crs=utm_crs,
            segment_length_m=road_segment_length_m,
            distance_damaged_m=distance_damaged_m
        )
    else:
        r_graded = gpd.GeoDataFrame([], crs="EPSG:4326")

    r_out_file = str(out_path / "roads_graded.geojson")
    r_graded.to_file(r_out_file, driver="GeoJSON")

    # Road km summary
    r_km_by_grade = (
        r_graded.groupby("damage_grade")["length_km"].sum().round(2).to_dict()
        if len(r_graded) > 0 else {}
    )
    r_km_by_type_grade = {}
    if len(r_graded) > 0:
        for (hwy, grp) in r_graded.groupby("highway"):
            r_km_by_type_grade[str(hwy)] = (
                grp.groupby("damage_grade")["length_km"].sum().round(2).to_dict()
            )

    # 6. Grade Bridges
    logger.info("Grading bridges...")
    br_file = osm_path / "osm_bridges.geojson"
    w_file = osm_path / "osm_waterways.geojson"
    raw_w = gpd.read_file(w_file) if w_file.exists() else None

    # Load hazard classes raster if present for fine-scale distance lookup
    haz_raster = None
    haz_raster_path = Path(hazard_polygons_path).parent / "hazard_classes.tif"
    if haz_raster_path.exists():
        with rasterio.open(haz_raster_path) as src_haz:
            haz_raster = src_haz.read(1)

    if br_file.exists():
        raw_br = gpd.read_file(br_file)
        br_graded = grade_bridges(
            bridges_gdf=raw_br,
            hazard_gdf=hazard_gdf,
            waterways_gdf=raw_w,
            hazard_raster=haz_raster,
            transform_matrix=trans,
            cloud_nodata_mask=cloud_or_nodata,
            inv_transform=inv_trans,
            utm_crs=utm_crs,
            bridge_distance_m=bridge_distance_m,
            bridge_reach_radius_m=bridge_reach_radius_m
        )
    else:
        br_graded = gpd.GeoDataFrame([], crs="EPSG:4326")

    br_out_file = str(out_path / "bridges_graded.geojson")
    br_graded.to_file(br_out_file, driver="GeoJSON")
    br_counts = br_graded["damage_grade"].value_counts().to_dict() if len(br_graded) > 0 else {}

    # 7. Render Quicklook
    out_quicklook = str(out_path / "quicklook_l4.png")
    logger.info(f"Rendering Layer 4 damage overview quicklook to {out_quicklook}...")
    render_l4_quicklook(
        s2_post_visual=s2_post_visual,
        buildings_gdf=b_graded,
        roads_gdf=r_graded,
        bridges_gdf=br_graded,
        hazard_gdf=hazard_gdf,
        output_png_path=out_quicklook,
        zoom_center_utm=None,
        zoom_half_width_m=2000.0,
        utm_crs=utm_crs,
        transform_matrix=trans
    )

    # 8. Damage Summary JSON
    damage_summary = {
        "status": "COMPLETED",
        "osm_coverage": coverage,
        "buildings": {
            "total_count": len(b_graded),
            "damage_grade_counts": b_counts,
            "evidence_counts": b_ev_counts,
            "affected_count": int(b_counts.get("Destroyed", 0) + b_counts.get("Damaged", 0) + b_counts.get("Possibly damaged", 0)),
            "parameters": {
                "overlap_destroyed_pct": building_overlap_pct,
                "distance_damaged_m": distance_damaged_m,
                "distance_possibly_damaged_m": distance_possibly_damaged_m
            }
        },
        "roads": {
            "total_segments": len(r_graded),
            "total_km": round(float(sum(r_km_by_grade.values())), 2) if r_km_by_grade else 0.0,
            "km_by_damage_grade": r_km_by_grade,
            "km_by_type_and_grade": r_km_by_type_grade,
            "segment_length_m": road_segment_length_m
        },
        "bridges": {
            "total_count": len(br_graded),
            "damage_grade_counts": br_counts,
            "rule_counts": br_graded["rule"].value_counts().to_dict() if len(br_graded) > 0 and "rule" in br_graded.columns else {},
            "evidence_counts": br_graded["evidence"].value_counts().to_dict() if len(br_graded) > 0 and "evidence" in br_graded.columns else {},
            "affected_count": int(br_counts.get("Destroyed", 0) + br_counts.get("Possibly damaged", 0)),
            "parameters": {
                "bridge_distance_m": bridge_distance_m,
                "bridge_reach_radius_m": bridge_reach_radius_m
            }
        },
        "outputs": {
            "buildings_graded": b_out_file,
            "roads_graded": r_out_file,
            "bridges_graded": br_out_file,
            "quicklook": out_quicklook
        }
    }

    out_json = str(out_path / "damage_summary.json")
    with open(out_json, "w") as f:
        json.dump(damage_summary, f, indent=2)

    logger.info(f"Layer 4 damage summary saved to {out_json}")
    return damage_summary


def main():
    parser = argparse.ArgumentParser(description="Run Layer 4 Critical Infrastructure Damage Grading")
    parser.add_argument("--config", default="configs/default.yaml", help="Path to config YAML")
    parser.add_argument("--bbox", type=float, nargs=4, default=None, help="Bounding box [min_lon, min_lat, max_lon, max_lat]")
    parser.add_argument("--utm-crs", default=None, help="Target UTM CRS")
    parser.add_argument("--osm-dir", default="data/raw/osm", help="Path to OSM directory")
    parser.add_argument("--hazard-polygons", default="data/processed/hazard_polygons.geojson", help="Path to hazard GeoJSON")
    parser.add_argument("--out-dir", default="data/processed", help="Output directory")

    args = parser.parse_args()

    bbox = args.bbox
    utm_crs = args.utm_crs
    building_overlap_pct = 50.0
    distance_damaged_m = 10.0
    distance_possibly_damaged_m = 30.0
    road_segment_length_m = 100.0
    bridge_distance_m = 30.0
    bridge_reach_radius_m = 100.0

    if args.config and os.path.exists(args.config):
        with open(args.config, "r") as f:
            cfg = yaml.safe_load(f)
        cs_cfg = cfg.get("case_study", {})
        if bbox is None:
            bbox = cs_cfg.get("bbox")
        if utm_crs is None:
            utm_crs = cs_cfg.get("utm_crs", "auto")

        dmg_cfg = cfg.get("damage_grading", {})
        building_overlap_pct = float(dmg_cfg.get("building_overlap_pct", building_overlap_pct))
        distance_damaged_m = float(dmg_cfg.get("distance_damaged_m", distance_damaged_m))
        distance_possibly_damaged_m = float(dmg_cfg.get("distance_possibly_damaged_m", distance_possibly_damaged_m))
        road_segment_length_m = float(dmg_cfg.get("road_segment_length_m", road_segment_length_m))
        bridge_distance_m = float(dmg_cfg.get("bridge_distance_m", bridge_distance_m))
        bridge_reach_radius_m = float(dmg_cfg.get("bridge_reach_radius_m", bridge_reach_radius_m))

    res = run_layer4(
        osm_dir=args.osm_dir,
        hazard_polygons_path=args.hazard_polygons,
        out_dir=args.out_dir,
        bbox=bbox,
        utm_crs=utm_crs,
        building_overlap_pct=building_overlap_pct,
        distance_damaged_m=distance_damaged_m,
        distance_possibly_damaged_m=distance_possibly_damaged_m,
        road_segment_length_m=road_segment_length_m,
        bridge_distance_m=bridge_distance_m,
        bridge_reach_radius_m=bridge_reach_radius_m
    )

    print("\n================== LAYER 4 DAMAGE GRADING SUMMARY ==================")
    print(f"Buildings (Total {res['buildings']['total_count']}): {res['buildings']['damage_grade_counts']}")
    print(f"Bridges (Total {res['bridges']['total_count']}):   {res['bridges']['damage_grade_counts']}")
    print(f"Roads km by Grade: {res['roads']['km_by_damage_grade']}")
    print(f"Damage Summary File: {res['outputs']['buildings_graded']}")


if __name__ == "__main__":
    main()

