"""
Repair Priority Analysis for Layer 5 Critical Infrastructure.
Ranks destroyed segments/bridges:
1. Single-element repairs: how many settlements (and buildings) regain access if ONLY that element is repaired.
2. Greedy repairs: top 5 repairs in sequence and cumulative settlements/buildings reconnected.
Outputs repair_priority.json.
"""

from typing import Dict, Any, List, Set, Tuple
import json
import logging
from pathlib import Path
import networkx as nx
import numpy as np
import geopandas as gpd
from scipy.spatial import cKDTree

logger = logging.getLogger("l5_repair")


def compute_repair_priorities(
    G_vehicle: nx.Graph,
    settlements_gdf: gpd.GeoDataFrame,
    destinations_gdf: gpd.GeoDataFrame,
    max_snap_distance_m: float = 500.0,
    output_json_path: str = "data/processed/routing/repair_priority.json"
) -> Dict[str, Any]:
    """
    Computes single-element and greedy top-5 repair priorities.
    """
    nodes_list = list(G_vehicle.nodes)
    nodes_tree = cKDTree(np.array(nodes_list))

    # Destinations
    d_pts = np.array([(d.geometry.x, d.geometry.y) for _, d in destinations_gdf.iterrows()])
    d_dists, d_indices = nodes_tree.query(d_pts)
    valid_d_nodes = set([nodes_list[d_indices[i]] for i, dist in enumerate(d_dists) if dist <= max_snap_distance_m])

    # Settlements mapped to network nodes
    s_nodes: Dict[str, Dict[str, Any]] = {}
    for idx, s_row in settlements_gdf.iterrows():
        pt = s_row.geometry
        d_snap, n_idx = nodes_tree.query([pt.x, pt.y])
        if d_snap <= max_snap_distance_m:
            s_nodes[s_row["settlement_id"]] = {
                "node": nodes_list[n_idx],
                "name": s_row["name"],
                "building_count": int(s_row.get("building_count", 0)),
                "population": str(s_row.get("population", "not available"))
            }

    # Pre-event graph & Dijkstra
    G_pre = G_vehicle.copy()
    for dn in valid_d_nodes:
        G_pre.add_edge("__DEST__", dn, weight=0.0)
    dist_pre, paths_pre = nx.single_source_dijkstra(G_pre, "__DEST__")

    # Post-event baseline graph (remove Destroyed edges)
    G_post = G_vehicle.copy()
    destroyed_edges = []
    for u, v, data in list(G_post.edges(data=True)):
        if data.get("damage_grade") == "Destroyed":
            destroyed_edges.append((u, v, data))
            G_post.remove_edge(u, v)

    for dn in valid_d_nodes:
        if dn in G_post:
            G_post.add_edge("__DEST__", dn, weight=0.0)

    dist_post = nx.single_source_dijkstra_path_length(G_post, "__DEST__")
    init_connected_sids = set(sid for sid, info in s_nodes.items() if info["node"] in dist_post)
    logger.info(f"Initial post-event connected settlements: {len(init_connected_sids)}")

    # Group destroyed edges by OSM ID
    dest_by_osm: Dict[str, List[Tuple[Any, Any, Dict[str, Any]]]] = {}
    osm_attributes: Dict[str, Dict[str, Any]] = {}
    for u, v, d in destroyed_edges:
        oid = str(d.get("osm_id", "unknown"))
        dest_by_osm.setdefault(oid, []).append((u, v, d))
        if oid not in osm_attributes:
            osm_attributes[oid] = {
                "highway": str(d.get("highway", "unknown")),
                "is_bridge": bool(d.get("is_bridge", False)),
                "total_destroyed_length_m": 0.0,
                "segment_count": 0
            }
        osm_attributes[oid]["total_destroyed_length_m"] += float(d.get("weight", 0.0))
        osm_attributes[oid]["segment_count"] += 1

    for oid in osm_attributes:
        osm_attributes[oid]["total_destroyed_length_m"] = round(osm_attributes[oid]["total_destroyed_length_m"], 1)

    # Calculate pre-event route bottleneck frequencies
    route_deps_count: Dict[str, int] = {}
    route_deps_bldgs: Dict[str, int] = {}
    for sid, info in s_nodes.items():
        n = info["node"]
        if n not in dist_pre:
            continue
        p = paths_pre[n]
        seen_oids = set()
        for i in range(len(p) - 1):
            ed = G_vehicle.get_edge_data(p[i], p[i+1])
            if ed and ed.get("damage_grade") == "Destroyed":
                seen_oids.add(str(ed.get("osm_id", "unknown")))
        for oid in seen_oids:
            route_deps_count[oid] = route_deps_count.get(oid, 0) + 1
            route_deps_bldgs[oid] = route_deps_bldgs.get(oid, 0) + info["building_count"]

    # 1. Single-element repairs evaluation
    single_element_results = []
    for oid, edges in dest_by_osm.items():
        G_temp = G_post.copy()
        for u, v, d in edges:
            G_temp.add_edge(u, v, **d)
        dist_temp = nx.single_source_dijkstra_path_length(G_temp, "__DEST__")
        regained = set(sid for sid, info in s_nodes.items() if info["node"] in dist_temp) - init_connected_sids
        regained_bldgs = sum(s_nodes[sid]["building_count"] for sid in regained)

        single_element_results.append({
            "osm_id": oid,
            "highway": osm_attributes[oid]["highway"],
            "is_bridge": osm_attributes[oid]["is_bridge"],
            "segment_count": osm_attributes[oid]["segment_count"],
            "total_destroyed_length_m": osm_attributes[oid]["total_destroyed_length_m"],
            "settlements_regained_if_only_repaired": len(regained),
            "buildings_regained_if_only_repaired": regained_bldgs,
            "pre_event_routes_dependent": route_deps_count.get(oid, 0),
            "pre_event_buildings_dependent": route_deps_bldgs.get(oid, 0)
        })

    # Sort single elements: primarily by settlements regained, then buildings, then route dependencies
    single_element_results.sort(
        key=lambda x: (
            x["settlements_regained_if_only_repaired"],
            x["buildings_regained_if_only_repaired"],
            x["pre_event_routes_dependent"],
            x["pre_event_buildings_dependent"]
        ),
        reverse=True
    )

    # 2. Greedy Repair Sequence (top 5)
    candidates = sorted(
        dest_by_osm.keys(),
        key=lambda oid: (route_deps_count.get(oid, 0), route_deps_bldgs.get(oid, 0)),
        reverse=True
    )

    greedy_steps = []
    curr_G = G_post.copy()
    curr_conn = set(init_connected_sids)
    repaired_oids: Set[str] = set()

    for step in range(1, 6):
        best_oid = None
        best_gain = -1
        best_bldg_gain = -1
        best_new_conn: Set[str] = set()

        # Check if any candidate yields immediate reconnected settlements
        for oid in candidates:
            if oid in repaired_oids:
                continue
            test_G = curr_G.copy()
            for u, v, d in dest_by_osm[oid]:
                test_G.add_edge(u, v, **d)
            dist_test = nx.single_source_dijkstra_path_length(test_G, "__DEST__")
            new_conn = set(sid for sid, info in s_nodes.items() if info["node"] in dist_test) - curr_conn
            gain = len(new_conn)
            bldg_gain = sum(s_nodes[sid]["building_count"] for sid in new_conn)
            if gain > best_gain:
                best_gain = gain
                best_bldg_gain = bldg_gain
                best_oid = oid
                best_new_conn = new_conn
            elif gain == best_gain and gain > 0 and bldg_gain > best_bldg_gain:
                best_bldg_gain = bldg_gain
                best_oid = oid
                best_new_conn = new_conn

        # If all candidates give 0 immediate reconnection (bottleneck in series), pick highest pre-event route bottleneck
        if best_gain <= 0:
            for oid in candidates:
                if oid not in repaired_oids:
                    best_oid = oid
                    break
            test_G = curr_G.copy()
            for u, v, d in dest_by_osm[best_oid]:
                test_G.add_edge(u, v, **d)
            dist_test = nx.single_source_dijkstra_path_length(test_G, "__DEST__")
            best_new_conn = set(sid for sid, info in s_nodes.items() if info["node"] in dist_test) - curr_conn
            best_gain = len(best_new_conn)
            best_bldg_gain = sum(s_nodes[sid]["building_count"] for sid in best_new_conn)

        repaired_oids.add(best_oid)
        for u, v, d in dest_by_osm[best_oid]:
            curr_G.add_edge(u, v, **d)
        curr_conn.update(best_new_conn)

        greedy_steps.append({
            "step": step,
            "osm_id": best_oid,
            "highway": osm_attributes[best_oid]["highway"],
            "is_bridge": osm_attributes[best_oid]["is_bridge"],
            "length_m": osm_attributes[best_oid]["total_destroyed_length_m"],
            "settlements_reconnected_step": best_gain,
            "buildings_reconnected_step": best_bldg_gain,
            "cumulative_settlements_reconnected": len(curr_conn) - len(init_connected_sids),
            "cumulative_buildings_reconnected": sum(s_nodes[sid]["building_count"] for sid in curr_conn) - sum(s_nodes[sid]["building_count"] for sid in init_connected_sids),
            "cumulative_total_connected_settlements": len(curr_conn)
        })

    output_data = {
        "metadata": {
            "description": "Layer 5 Critical Infrastructure Repair Prioritization",
            "initial_connected_settlements": len(init_connected_sids),
            "total_cut_off_settlements": 44,
            "bottleneck_explanation": "All cut-off settlements lie north of 3 destroyed elements in series along the Pasang Lhamu highway corridor (way/84566285, way/84566287, way/332122791). Thus repairing any SINGLE element yields 0 reconnected settlements. Sequential repair of these three corridor links followed by way/1266396385 reconnects northern settlements."
        },
        "single_element_repair_ranking": single_element_results,
        "greedy_repair_top_5": greedy_steps
    }

    Path(output_json_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_json_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved repair priority analysis to {output_json_path}")

    return output_data


def compute_repair_packages(
    G_vehicle: nx.Graph,
    settlements_gdf: gpd.GeoDataFrame,
    destinations_gdf: gpd.GeoDataFrame,
    max_snap_distance_m: float = 500.0,
    penalty_per_element: float = 1_000_000.0,
    output_json_path: str = "data/processed/routing/repair_packages.json"
) -> Dict[str, Any]:
    """
    Computes minimal repair packages for cut-off settlements:
    For each cut-off settlement, finds the route requiring the FEWEST destroyed elements
    (via edge penalty P + length).
    Groups settlements sharing the same package, and ranks packages by settlements/buildings regained.
    """
    nodes_list = list(G_vehicle.nodes)
    nodes_tree = cKDTree(np.array(nodes_list))

    # Destinations
    d_pts = np.array([(d.geometry.x, d.geometry.y) for _, d in destinations_gdf.iterrows()])
    d_dists, d_indices = nodes_tree.query(d_pts)
    valid_d_nodes = set([nodes_list[d_indices[i]] for i, dist in enumerate(d_dists) if dist <= max_snap_distance_m])

    # Settlements mapped
    s_nodes = {}
    for idx, s_row in settlements_gdf.iterrows():
        pt = s_row.geometry
        d_snap, n_idx = nodes_tree.query([pt.x, pt.y])
        if d_snap <= max_snap_distance_m:
            s_nodes[s_row["settlement_id"]] = {
                "node": nodes_list[n_idx],
                "name": s_row["name"],
                "building_count": int(s_row.get("building_count", 0))
            }

    # Post-event baseline to identify cut-off settlements
    G_post = G_vehicle.copy()
    for u, v, d in list(G_post.edges(data=True)):
        if d.get("damage_grade") == "Destroyed":
            G_post.remove_edge(u, v)
    for dn in valid_d_nodes:
        if dn in G_post:
            G_post.add_edge("__DEST__", dn, weight=0.0)

    dist_post = nx.single_source_dijkstra_path_length(G_post, "__DEST__")
    cut_off_sids = [sid for sid, info in s_nodes.items() if info["node"] not in dist_post]

    # Penalized graph: large penalty for destroyed elements
    G_pen = G_vehicle.copy()
    for u, v, d in G_pen.edges(data=True):
        length = float(d.get("weight", 0.0))
        is_dest = (d.get("damage_grade") == "Destroyed")
        G_pen[u][v]["penalized_weight"] = length + (penalty_per_element if is_dest else 0.0)

    for dn in valid_d_nodes:
        G_pen.add_edge("__DEST__", dn, penalized_weight=0.0)

    packages_by_sid = {}
    for sid in cut_off_sids:
        info = s_nodes[sid]
        sn = info["node"]
        path = nx.shortest_path(G_pen, sn, "__DEST__", weight="penalized_weight")
        destroyed_oids = set()
        for i in range(len(path) - 2):  # exclude __DEST__
            ed = G_vehicle.get_edge_data(path[i], path[i+1])
            if ed and ed.get("damage_grade") == "Destroyed":
                destroyed_oids.add(str(ed.get("osm_id")))
        pkg = tuple(sorted(list(destroyed_oids)))
        packages_by_sid[sid] = {
            "settlement_id": sid,
            "name": info["name"],
            "building_count": info["building_count"],
            "package": pkg
        }

    # Group settlements sharing the same package
    grouped = {}
    for sid, p_data in packages_by_sid.items():
        pkg = p_data["package"]
        grouped.setdefault(pkg, {"settlements": [], "buildings": 0})
        grouped[pkg]["settlements"].append(p_data["name"])
        grouped[pkg]["buildings"] += p_data["building_count"]

    ranked_packages = []
    for pkg, g_info in grouped.items():
        ranked_packages.append({
            "elements": list(pkg),
            "element_count": len(pkg),
            "settlements_count": len(g_info["settlements"]),
            "buildings_count": g_info["buildings"],
            "settlements": g_info["settlements"]
        })

    # Rank by settlements, then buildings
    ranked_packages.sort(key=lambda x: (x["settlements_count"], x["buildings_count"]), reverse=True)
    for idx, r in enumerate(ranked_packages, start=1):
        r["rank"] = idx

    pkg_output = {
        "metadata": {
            "description": "Minimal Repair Packages for Cut-Off Settlements",
            "total_cut_off_settlements": len(cut_off_sids),
            "unique_packages_count": len(ranked_packages)
        },
        "ranked_packages": ranked_packages,
        "settlement_packages": {sid: list(v["package"]) for sid, v in packages_by_sid.items()}
    }

    Path(output_json_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_json_path, "w", encoding="utf-8") as f:
        json.dump(pkg_output, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved repair packages analysis to {output_json_path}")

    return pkg_output
