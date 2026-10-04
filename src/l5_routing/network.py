"""
Network Graph Construction for Layer 5 Routing.
Builds topological routing graphs for VEHICLE and WALKING networks
conditioned on Layer 4 critical infrastructure damage classifications.
"""

import logging
from typing import List, Dict, Any, Tuple, Set, Optional
import networkx as nx
import numpy as np
import geopandas as gpd
from shapely.geometry import Point, LineString, box

logger = logging.getLogger("l5_network")


def build_routing_networks(
    roads_path: str = "data/raw/osm_buffered/osm_roads.geojson",
    hazard_roads_path: str = "data/processed/roads_graded.geojson",
    hazard_bridges_path: str = "data/processed/bridges_graded.geojson",
    bbox: List[float] = [85.30, 28.10, 85.42, 28.25],
    vehicle_highways: Optional[List[str]] = None,
    walking_highways_extra: Optional[List[str]] = None,
    rural_roads_drivable: bool = False,
    utm_crs: str = "EPSG:32645"
) -> Dict[str, Any]:
    """
    Constructs VEHICLE and WALKING NetworkX graphs with Layer 4 damage overlays.
    """
    if vehicle_highways is None:
        vehicle_highways = [
            "motorway", "trunk", "primary", "secondary", "tertiary",
            "unclassified", "residential", "service",
            "motorway_link", "trunk_link", "primary_link", "secondary_link", "tertiary_link"
        ]
    if walking_highways_extra is None:
        walking_highways_extra = ["path", "footway", "track", "steps", "pedestrian", "cycleway"]

    v_types = set(vehicle_highways)
    if rural_roads_drivable:
        v_types.update(["track", "unclassified"])
    w_types = v_types.union(set(walking_highways_extra))

    bbox_deg = box(*bbox)
    bbox_utm = gpd.GeoSeries([bbox_deg], crs="EPSG:4326").to_crs(utm_crs).iloc[0]

    logger.info(f"Loading buffered roads from {roads_path}...")
    roads_gdf = gpd.read_file(roads_path).to_crs(utm_crs)

    # Load Layer 4 damage classifications inside study bbox
    r_graded = gpd.read_file(hazard_roads_path).to_crs(utm_crs)
    br_graded = gpd.read_file(hazard_bridges_path).to_crs(utm_crs)

    r_dest = r_graded[r_graded["damage_grade"] == "Destroyed"]
    br_dest = br_graded[br_graded["damage_grade"] == "Destroyed"]
    dest_union = r_dest.union_all()
    if len(br_dest) > 0:
        dest_union = dest_union.union(br_dest.union_all()) if dest_union is not None and not dest_union.is_empty else br_dest.union_all()

    r_poss = r_graded[r_graded["damage_grade"] == "Possibly damaged"]
    br_poss = br_graded[br_graded["damage_grade"] == "Possibly damaged"]
    poss_union = r_poss.union_all()
    if len(br_poss) > 0:
        poss_union = poss_union.union(br_poss.union_all()) if poss_union is not None and not poss_union.is_empty else br_poss.union_all()

    r_cloud = r_graded[r_graded["damage_grade"] == "Unknown (cloud)"]
    br_cloud = br_graded[br_graded["damage_grade"] == "Unknown (cloud)"]
    cloud_union = r_cloud.union_all() if len(r_cloud) > 0 else None
    if len(br_cloud) > 0:
        cloud_union = cloud_union.union(br_cloud.union_all()) if cloud_union is not None and not cloud_union.is_empty else br_cloud.union_all()

    G_vehicle = nx.Graph()
    G_walking = nx.Graph()

    # Edge tracking
    edge_stats = {
        "vehicle": {"total": 0, "destroyed": 0, "possibly_damaged": 0, "unknown_cloud": 0, "intact": 0},
        "walking": {"total": 0, "destroyed": 0, "possibly_damaged": 0, "unknown_cloud": 0, "intact": 0}
    }

    for idx, row in roads_gdf.iterrows():
        geom = row.geometry
        if geom is None or geom.is_empty:
            continue
        hwy = str(row.get("highway", "unclassified"))
        oid = str(row.get("@osmId", f"way_{idx}"))
        is_bridge = (str(row.get("bridge")) not in ["None", "no", "nan", ""])

        is_v = hwy in v_types
        is_w = hwy in w_types
        if not is_v and not is_w:
            continue

        in_bbox = geom.intersects(bbox_utm)
        lines = [geom] if geom.geom_type == "LineString" else geom.geoms

        for l in lines:
            coords = list(l.coords)
            for i in range(len(coords) - 1):
                p1 = (round(coords[i][0], 1), round(coords[i][1], 1))
                p2 = (round(coords[i+1][0], 1), round(coords[i+1][1], 1))
                length_m = float(np.hypot(p2[0] - p1[0], p2[1] - p1[1]))
                if length_m == 0:
                    continue

                damage_grade = "Not affected"
                if in_bbox:
                    seg = LineString([p1, p2])
                    if dest_union is not None and not dest_union.is_empty and seg.distance(dest_union) <= 5.0:
                        damage_grade = "Destroyed"
                    elif poss_union is not None and not poss_union.is_empty and seg.distance(poss_union) <= 5.0:
                        damage_grade = "Possibly damaged"
                    elif cloud_union is not None and not cloud_union.is_empty and seg.distance(cloud_union) <= 5.0:
                        damage_grade = "Unknown (cloud)"

                e_attr = {
                    "weight": length_m,
                    "highway": hwy,
                    "osm_id": oid,
                    "damage_grade": damage_grade,
                    "is_bridge": is_bridge,
                    "coords": [p1, p2]
                }

                if is_v:
                    G_vehicle.add_edge(p1, p2, **e_attr)
                    edge_stats["vehicle"]["total"] += 1
                    if damage_grade == "Destroyed":
                        edge_stats["vehicle"]["destroyed"] += 1
                    elif damage_grade == "Possibly damaged":
                        edge_stats["vehicle"]["possibly_damaged"] += 1
                    elif damage_grade == "Unknown (cloud)":
                        edge_stats["vehicle"]["unknown_cloud"] += 1
                    else:
                        edge_stats["vehicle"]["intact"] += 1

                if is_w:
                    G_walking.add_edge(p1, p2, **e_attr)
                    edge_stats["walking"]["total"] += 1
                    if damage_grade == "Destroyed":
                        edge_stats["walking"]["destroyed"] += 1
                    elif damage_grade == "Possibly damaged":
                        edge_stats["walking"]["possibly_damaged"] += 1
                    elif damage_grade == "Unknown (cloud)":
                        edge_stats["walking"]["unknown_cloud"] += 1
                    else:
                        edge_stats["walking"]["intact"] += 1

    logger.info(f"Vehicle Graph built: {G_vehicle.number_of_nodes()} nodes, {G_vehicle.number_of_edges()} edges ({edge_stats['vehicle']['destroyed']} destroyed)")
    logger.info(f"Walking Graph built: {G_walking.number_of_nodes()} nodes, {G_walking.number_of_edges()} edges ({edge_stats['walking']['destroyed']} destroyed)")

    return {
        "G_vehicle": G_vehicle,
        "G_walking": G_walking,
        "edge_stats": edge_stats,
        "dest_union": dest_union,
        "poss_union": poss_union,
        "cloud_union": cloud_union
    }
