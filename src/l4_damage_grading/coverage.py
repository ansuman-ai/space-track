"""
OpenStreetMap Pre-Event Exposure Coverage Module.
Quantifies baseline infrastructure within the study area bounding box:
buildings, bridges, healthcare facilities, and road network km by highway classification.
"""

from pathlib import Path
from typing import Dict, Any, List, Optional
import geopandas as gpd
from shapely.geometry import box
import numpy as np


def compute_osm_coverage(
    osm_dir: str = "data/raw/osm",
    bbox: Optional[List[float]] = None,
    utm_crs: str = "EPSG:32645"
) -> Dict[str, Any]:
    """
    Computes pre-event infrastructure exposure within the bounding box.
    Returns feature counts and road network length in km by type.
    """
    osm_path = Path(osm_dir)
    bbox_poly = box(*bbox) if bbox is not None else None

    # 1. Buildings
    b_file = osm_path / "osm_buildings.geojson"
    if b_file.exists():
        b_gdf = gpd.read_file(b_file)
        if bbox_poly is not None:
            b_in_bbox = b_gdf[b_gdf.intersects(bbox_poly)]
        else:
            b_in_bbox = b_gdf
        total_buildings = len(b_in_bbox)
    else:
        total_buildings = 0

    # 2. Bridges
    br_file = osm_path / "osm_bridges.geojson"
    if br_file.exists():
        br_gdf = gpd.read_file(br_file)
        if bbox_poly is not None:
            br_in_bbox = br_gdf[br_gdf.intersects(bbox_poly)]
        else:
            br_in_bbox = br_gdf
        total_bridges = len(br_in_bbox)
    else:
        total_bridges = 0

    # 3. Hospitals
    h_file = osm_path / "osm_hospitals.geojson"
    if h_file.exists():
        h_gdf = gpd.read_file(h_file)
        if bbox_poly is not None:
            h_in_bbox = h_gdf[h_gdf.intersects(bbox_poly)]
        else:
            h_in_bbox = h_gdf
        total_hospitals = len(h_in_bbox)
    else:
        total_hospitals = 0

    # 4. Roads
    r_file = osm_path / "osm_roads.geojson"
    road_km_by_type = {}
    road_perimeter_km_by_type = {}
    total_road_km = 0.0
    total_road_perimeter_km = 0.0

    if r_file.exists():
        r_gdf = gpd.read_file(r_file)
        if bbox_poly is not None:
            r_in_bbox = r_gdf[r_gdf.intersects(bbox_poly)].copy()
        else:
            r_in_bbox = r_gdf.copy()

        # Project to metric CRS for accurate geodesic distances
        r_utm = r_in_bbox.to_crs(utm_crs)

        # Standard perimeter length in GeoPandas
        perims_km = r_utm.length / 1000.0
        r_utm["perimeter_km"] = perims_km

        lens_km = []
        for geom in r_utm.geometry:
            if geom is not None and geom.geom_type in ["LineString", "MultiLineString"]:
                lens_km.append(geom.length / 1000.0)
            elif geom is not None:
                minx, miny, maxx, maxy = geom.bounds
                lens_km.append(np.hypot(maxx - minx, maxy - miny) / 1000.0)
            else:
                lens_km.append(0.0)
        r_utm["centerline_km"] = lens_km

        for hwy, grp in r_utm.groupby("highway"):
            road_km_by_type[str(hwy)] = round(float(grp["centerline_km"].sum()), 2)
            road_perimeter_km_by_type[str(hwy)] = round(float(grp["perimeter_km"].sum()), 2)

        total_road_km = round(float(r_utm["centerline_km"].sum()), 2)
        total_road_perimeter_km = round(float(r_utm["perimeter_km"].sum()), 2)

    coverage_summary = {
        "buildings_count": total_buildings,
        "bridges_count": total_bridges,
        "hospitals_count": total_hospitals,
        "road_km_total": total_road_km,
        "road_km_by_type": road_km_by_type,
        "road_perimeter_km_total": total_road_perimeter_km,
        "road_perimeter_km_by_type": road_perimeter_km_by_type,
        "bbox": bbox,
    }

    return coverage_summary
