"""
Network Graph Construction for Layer 5 Routing.
Builds topological routing graphs for VEHICLE and WALKING networks
conditioned on Layer 4 critical infrastructure damage classifications.
Reuses base topological graphs across scenarios and updates edge damage grades.
"""

import logging
from typing import List, Dict, Any, Tuple, Set, Optional
import networkx as nx
import numpy as np
import geopandas as gpd
from shapely.geometry import Point, LineString, box

logger = logging.getLogger("l5_network")

import threading
_ROADS_GDF_CACHE: Dict[Tuple[str, str], gpd.GeoDataFrame] = {}
_BASE_NETWORKS_CACHE: Dict[Any, Tuple[nx.Graph, nx.Graph, List[Any], List[Any]]] = {}
_BASE_NETWORKS_LOCK = threading.Lock()


def clear_networks_cache():
    """Clears cached base graphs and road geodataframes to reclaim memory."""
    with _BASE_NETWORKS_LOCK:
        _ROADS_GDF_CACHE.clear()
        _BASE_NETWORKS_CACHE.clear()


def get_base_network(
    roads_path: str,
    bbox: List[float],
    vehicle_highways: Optional[List[str]] = None,
    walking_highways_extra: Optional[List[str]] = None,
    rural_roads_drivable: bool = False,
    construction_roads_passable: bool = False,
    snap_dead_end_nodes_m: float = 0.0,
    utm_crs: Optional[str] = None
) -> Tuple[nx.Graph, nx.Graph, List[Any], List[Any]]:
    """Constructs and caches the base topological graphs without damage overlays."""
    if utm_crs is None or utm_crs == "auto":
        from src.common.crs_utils import auto_utm_crs
        utm_crs = auto_utm_crs(bbox)
    cache_key = (
        roads_path,
        tuple(bbox) if bbox else None,
        tuple(vehicle_highways) if vehicle_highways else None,
        tuple(walking_highways_extra) if walking_highways_extra else None,
        rural_roads_drivable,
        construction_roads_passable,
        snap_dead_end_nodes_m,
        utm_crs
    )
    with _BASE_NETWORKS_LOCK:
        if cache_key in _BASE_NETWORKS_CACHE:
            return _BASE_NETWORKS_CACHE[cache_key]

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
    if construction_roads_passable:
        v_types.add("construction")
    w_types = v_types.union(set(walking_highways_extra))

    bbox_deg = box(*bbox)
    bbox_utm = gpd.GeoSeries([bbox_deg], crs="EPSG:4326").to_crs(utm_crs).iloc[0]

    gdf_key = (roads_path, utm_crs)
    if gdf_key in _ROADS_GDF_CACHE:
        roads_gdf = _ROADS_GDF_CACHE[gdf_key]
    else:
        logger.info(f"Loading buffered roads from {roads_path}...")
        roads_gdf = gpd.read_file(roads_path).to_crs(utm_crs)
        _ROADS_GDF_CACHE[gdf_key] = roads_gdf

    G_vehicle = nx.Graph()
    G_walking = nx.Graph()
    bbox_edges_v = []
    bbox_edges_w = []

    for idx, row in roads_gdf.iterrows():
        geom = row.geometry
        if geom is None or geom.is_empty:
            continue
        hwy = str(row.get("highway", "unclassified"))
        oid = str(row.get("@osmId", f"way_{idx}"))
        is_bridge = (str(row.get("bridge")) not in ["None", "no", "nan", ""])

        constr_sub = str(row.get("construction", ""))
        is_v = (hwy in v_types) or (construction_roads_passable and (hwy == "construction" or constr_sub in v_types))
        is_w = (hwy in w_types) or (construction_roads_passable and (hwy == "construction" or constr_sub in w_types))
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

                seg = LineString([p1, p2]) if in_bbox else None
                e_attr = {
                    "weight": length_m,
                    "highway": hwy,
                    "construction": constr_sub,
                    "osm_id": oid,
                    "damage_grade": "Not affected",
                    "is_bridge": is_bridge,
                    "coords": [p1, p2]
                }

                if is_v:
                    G_vehicle.add_edge(p1, p2, **e_attr)
                    if in_bbox:
                        bbox_edges_v.append((p1, p2, seg))

                if is_w:
                    G_walking.add_edge(p1, p2, **e_attr)
                    if in_bbox:
                        bbox_edges_w.append((p1, p2, seg))

    if snap_dead_end_nodes_m > 0.0:
        from scipy.spatial import cKDTree
        # Snap vehicle dead ends
        v_nodes = list(G_vehicle.nodes)
        if v_nodes:
            v_tree = cKDTree(np.array(v_nodes))
            dead_ends = [n for n in G_vehicle.nodes if G_vehicle.degree(n) == 1]
            snap_count = 0
            for n in dead_ends:
                ball = v_tree.query_ball_point([n[0], n[1]], r=snap_dead_end_nodes_m)
                g_neighbors = set(G_vehicle.neighbors(n))
                g_neighbors.add(n)
                for idx in ball:
                    other_n = v_nodes[idx]
                    if other_n not in g_neighbors:
                        d = float(np.hypot(n[0] - other_n[0], n[1] - other_n[1]))
                        G_vehicle.add_edge(n, other_n, weight=d, highway="connector", damage_grade="Not affected", is_bridge=False, osm_id="snap_connector")
                        snap_count += 1
            logger.info(f"Snapped {snap_count} dead-end nodes within {snap_dead_end_nodes_m} m in Vehicle network.")

    res = (G_vehicle, G_walking, bbox_edges_v, bbox_edges_w)
    with _BASE_NETWORKS_LOCK:
        _BASE_NETWORKS_CACHE[cache_key] = res
    return res


def build_routing_networks(
    roads_path: str = "data/raw/osm_buffered/osm_roads.geojson",
    hazard_roads_path: str = "data/processed/roads_graded.geojson",
    hazard_bridges_path: str = "data/processed/bridges_graded.geojson",
    bbox: List[float] = None,
    vehicle_highways: Optional[List[str]] = None,
    walking_highways_extra: Optional[List[str]] = None,
    rural_roads_drivable: bool = False,
    construction_roads_passable: bool = False,
    snap_dead_end_nodes_m: float = 0.0,
    utm_crs: Optional[str] = None
) -> Dict[str, Any]:
    """
    Constructs VEHICLE and WALKING NetworkX graphs with Layer 4 damage overlays.
    Reuses cached base graph topology across scenarios.
    """
    if utm_crs is None or utm_crs == "auto":
        from src.common.crs_utils import auto_utm_crs
        utm_crs = auto_utm_crs(bbox)

    # 1. Base network
    G_v_base, G_w_base, bbox_edges_v, bbox_edges_w = get_base_network(
        roads_path=roads_path,
        bbox=bbox,
        vehicle_highways=vehicle_highways,
        walking_highways_extra=walking_highways_extra,
        rural_roads_drivable=rural_roads_drivable,
        construction_roads_passable=construction_roads_passable,
        snap_dead_end_nodes_m=snap_dead_end_nodes_m,
        utm_crs=utm_crs
    )

    # 2. Damage classifications inside bbox
    r_graded = gpd.read_file(hazard_roads_path).to_crs(utm_crs)
    br_graded = gpd.read_file(hazard_bridges_path).to_crs(utm_crs)

    r_dest = r_graded[r_graded["damage_grade"].isin(["Destroyed", "Flooded / impassable"])]
    br_dest = br_graded[br_graded["damage_grade"].isin(["Destroyed", "Flooded / impassable"])]
    dest_union = r_dest.union_all()
    if len(br_dest) > 0:
        dest_union = dest_union.union(br_dest.union_all()) if dest_union is not None and not dest_union.is_empty else br_dest.union_all()

    r_poss = r_graded[r_graded["damage_grade"].isin(["Possibly damaged", "Possibly flooded"])]
    br_poss = br_graded[br_graded["damage_grade"].isin(["Possibly damaged", "Possibly flooded"])]
    poss_union = r_poss.union_all()
    if len(br_poss) > 0:
        poss_union = poss_union.union(br_poss.union_all()) if poss_union is not None and not poss_union.is_empty else br_poss.union_all()

    r_cloud = r_graded[r_graded["damage_grade"] == "Unknown (cloud)"]
    br_cloud = br_graded[br_graded["damage_grade"] == "Unknown (cloud)"]
    cloud_union = r_cloud.union_all() if len(r_cloud) > 0 else None
    if len(br_cloud) > 0:
        cloud_union = cloud_union.union(br_cloud.union_all()) if cloud_union is not None and not cloud_union.is_empty else br_cloud.union_all()

    # 3. Copy base graphs and apply damage grades on bbox edges
    G_vehicle = G_v_base.copy()
    G_walking = G_w_base.copy()

    edge_stats = {
        "vehicle": {"total": G_vehicle.number_of_edges(), "destroyed": 0, "possibly_damaged": 0, "unknown_cloud": 0, "intact": 0},
        "walking": {"total": G_walking.number_of_edges(), "destroyed": 0, "possibly_damaged": 0, "unknown_cloud": 0, "intact": 0}
    }

    for p1, p2, seg in bbox_edges_v:
        damage_grade = "Not affected"
        if dest_union is not None and not dest_union.is_empty and seg.distance(dest_union) <= 5.0:
            damage_grade = "Destroyed"
            edge_stats["vehicle"]["destroyed"] += 1
        elif poss_union is not None and not poss_union.is_empty and seg.distance(poss_union) <= 5.0:
            damage_grade = "Possibly damaged"
            edge_stats["vehicle"]["possibly_damaged"] += 1
        elif cloud_union is not None and not cloud_union.is_empty and seg.distance(cloud_union) <= 5.0:
            damage_grade = "Unknown (cloud)"
            edge_stats["vehicle"]["unknown_cloud"] += 1
        G_vehicle[p1][p2]["damage_grade"] = damage_grade

    edge_stats["vehicle"]["intact"] = edge_stats["vehicle"]["total"] - (
        edge_stats["vehicle"]["destroyed"] + edge_stats["vehicle"]["possibly_damaged"] + edge_stats["vehicle"]["unknown_cloud"]
    )

    for p1, p2, seg in bbox_edges_w:
        damage_grade = "Not affected"
        if dest_union is not None and not dest_union.is_empty and seg.distance(dest_union) <= 5.0:
            damage_grade = "Destroyed"
            edge_stats["walking"]["destroyed"] += 1
        elif poss_union is not None and not poss_union.is_empty and seg.distance(poss_union) <= 5.0:
            damage_grade = "Possibly damaged"
            edge_stats["walking"]["possibly_damaged"] += 1
        elif cloud_union is not None and not cloud_union.is_empty and seg.distance(cloud_union) <= 5.0:
            damage_grade = "Unknown (cloud)"
            edge_stats["walking"]["unknown_cloud"] += 1
        G_walking[p1][p2]["damage_grade"] = damage_grade

    edge_stats["walking"]["intact"] = edge_stats["walking"]["total"] - (
        edge_stats["walking"]["destroyed"] + edge_stats["walking"]["possibly_damaged"] + edge_stats["walking"]["unknown_cloud"]
    )

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
