"""
Connectivity and Route Severance Analysis for Layer 5.
Evaluates pre- and post-event connectivity from settlements to destinations
across VEHICLE and WALKING networks under Optimistic and Pessimistic scenarios.
Strict 3-value status classification:
1. 'cut off'
2. 'connected (route verified clear)'
3. 'connected (unverified: route passes cloud-covered segments)'
(plus 'no_network_access' / 'isolated_pre_event' for settlements with no network pre-event).
"""

from typing import List, Dict, Any, Tuple, Optional, Set
import networkx as nx
import numpy as np
import geopandas as gpd
from shapely.geometry import Point, LineString
from scipy.spatial import cKDTree


def find_all_breaking_edges(
    G: nx.Graph,
    path_from_source: List[Tuple[float, float]],
    blocked_grades: Set[str]
) -> List[Dict[str, Any]]:
    """
    Finds ALL severed infrastructure elements along the pre-event path from source.
    """
    breaks = []
    nodes = [n for n in path_from_source if n != "__DEST__"]
    for i in range(len(nodes) - 1):
        u = nodes[i]
        v = nodes[i + 1]
        e_data = G.get_edge_data(u, v)
        if e_data:
            grade = e_data.get("damage_grade", "Not affected")
            if grade in blocked_grades:
                breaks.append({
                    "osm_id": str(e_data.get("osm_id", "unknown")),
                    "highway": str(e_data.get("highway", "unknown")),
                    "is_bridge": bool(e_data.get("is_bridge", False)),
                    "damage_grade": str(grade),
                    "length_m": round(float(e_data.get("weight", 0.0)), 1),
                    "coords": [u, v]
                })
    return breaks


def find_breaking_edge(
    G: nx.Graph,
    path_from_source: List[Tuple[float, float]],
    blocked_grades: Set[str]
) -> Optional[Dict[str, Any]]:
    """
    Finds the first severed infrastructure element along the pre-event path.
    Maintained for backwards compatibility.
    """
    all_b = find_all_breaking_edges(G, path_from_source, blocked_grades)
    return all_b[0] if all_b else None


from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra


def _solve_scenario_csgraph(
    G: nx.Graph,
    nodes_list: List[Any],
    node_to_idx: Dict[Any, int],
    dest_idx: int,
    valid_d_nodes: Set[Any],
    blocked_grades: Optional[Set[str]] = None
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Solves multi-source Dijkstra from __DEST__ using scipy.sparse.csgraph.
    Returns (dist_arr, pred_arr).
    """
    rows = []
    cols = []
    weights = []
    for u, v, data in G.edges(data=True):
        grade = data.get("damage_grade", "Not affected")
        if blocked_grades and grade in blocked_grades:
            continue
        u_idx = node_to_idx[u]
        v_idx = node_to_idx[v]
        w = float(data.get("weight", 0.0))
        rows.extend([u_idx, v_idx])
        cols.extend([v_idx, u_idx])
        weights.extend([w, w])

    for d_node in valid_d_nodes:
        d_idx = node_to_idx[d_node]
        rows.extend([dest_idx, d_idx])
        cols.extend([d_idx, dest_idx])
        weights.extend([0.0, 0.0])

    n_total = len(nodes_list) + 1
    csr = csr_matrix((weights, (rows, cols)), shape=(n_total, n_total), dtype=np.float64)
    dist_arr, pred_arr = dijkstra(csr, directed=False, indices=dest_idx, return_predecessors=True)
    return dist_arr, pred_arr


def _reconstruct_path_to_dest(
    s_idx: int,
    dest_idx: int,
    nodes_list: List[Any],
    pred_arr: np.ndarray
) -> List[Any]:
    path = []
    curr = s_idx
    while curr != dest_idx and curr != -9999:
        path.append(nodes_list[curr])
        curr = pred_arr[curr]
    if curr == dest_idx:
        path.append("__DEST__")
        return path
    return []


def evaluate_network_connectivity(
    G: nx.Graph,
    settlements_gdf: gpd.GeoDataFrame,
    destinations_gdf: gpd.GeoDataFrame,
    network_name: str = "vehicle",
    max_snap_distance_m: float = 500.0
) -> Dict[str, Any]:
    """
    Computes pre-event and post-event connectivity across optimistic and pessimistic scenarios
    using multi-source Dijkstra from all destinations via scipy.sparse.csgraph.
    """
    nodes_list = list(G.nodes)
    if len(nodes_list) == 0:
        return {"error": "Empty graph"}

    nodes_arr = np.array(nodes_list)
    nodes_tree = cKDTree(nodes_arr)
    node_to_idx = {n: i for i, n in enumerate(nodes_list)}
    dest_idx = len(nodes_list)

    # 1. Snap Destinations
    d_pts = np.array([(d.geometry.x, d.geometry.y) for _, d in destinations_gdf.iterrows()])
    d_dists, d_indices = nodes_tree.query(d_pts)
    valid_d_nodes = set()
    for i, dist in enumerate(d_dists):
        if dist <= max_snap_distance_m:
            valid_d_nodes.add(nodes_list[d_indices[i]])

    # 2. Multi-source Dijkstra from __DEST__ using scipy.sparse.csgraph
    dist_pre, pred_pre = _solve_scenario_csgraph(G, nodes_list, node_to_idx, dest_idx, valid_d_nodes, blocked_grades=None)
    dist_opt, pred_opt = _solve_scenario_csgraph(G, nodes_list, node_to_idx, dest_idx, valid_d_nodes, blocked_grades={"Destroyed"})
    dist_pess, pred_pess = _solve_scenario_csgraph(G, nodes_list, node_to_idx, dest_idx, valid_d_nodes, blocked_grades={"Destroyed", "Possibly damaged"})

    # 3. Evaluate Each Settlement
    s_results = []
    cut_off_optimistic = []
    cut_off_pessimistic = []
    connected_clear_opt = []
    connected_unverified_opt = []
    connected_clear_pess = []
    connected_unverified_pess = []
    no_access_list = []

    for idx, s_row in settlements_gdf.iterrows():
        s_id = s_row["settlement_id"]
        s_name = s_row["name"]
        b_count = int(s_row.get("building_count", 0))
        pop = str(s_row.get("population", "not available"))
        geom = s_row.geometry

        # Snap settlement
        d_snap, n_idx = nodes_tree.query([geom.x, geom.y])
        if d_snap > max_snap_distance_m:
            res = {
                "settlement_id": s_id,
                "name": s_name,
                "building_count": b_count,
                "population": pop,
                "snap_distance_m": round(float(d_snap), 1),
                "status_optimistic": "no_network_access",
                "status_pessimistic": "no_network_access",
                "pre_distance_km": None,
                "post_distance_opt_km": None,
                "post_distance_pess_km": None,
                "detour_opt_km": None,
                "detour_pess_km": None,
                "breaks_opt": [],
                "breaks_pess": [],
                "broken_element_opt": None,
                "broken_element_pess": None,
                "pre_path": []
            }
            s_results.append(res)
            no_access_list.append(s_id)
            continue

        s_node = nodes_list[n_idx]
        can_pre = not np.isinf(dist_pre[n_idx])

        if not can_pre:
            res = {
                "settlement_id": s_id,
                "name": s_name,
                "building_count": b_count,
                "population": pop,
                "snap_distance_m": round(float(d_snap), 1),
                "status_optimistic": "isolated_pre_event",
                "status_pessimistic": "isolated_pre_event",
                "pre_distance_km": None,
                "post_distance_opt_km": None,
                "post_distance_pess_km": None,
                "detour_opt_km": None,
                "detour_pess_km": None,
                "breaks_opt": [],
                "breaks_pess": [],
                "broken_element_opt": None,
                "broken_element_pess": None,
                "pre_path": []
            }
            s_results.append(res)
            no_access_list.append(s_id)
            continue

        pre_dist_m = float(dist_pre[n_idx])
        pre_dist_km = round(pre_dist_m / 1000.0, 3)
        path_from_s = _reconstruct_path_to_dest(n_idx, dest_idx, nodes_list, pred_pre)

        # Optimistic scenario
        can_opt = not np.isinf(dist_opt[n_idx])
        if can_opt:
            post_dist_opt_km = round(float(dist_opt[n_idx]) / 1000.0, 3)
            detour_opt_km = round(max(0.0, post_dist_opt_km - pre_dist_km), 3)
            breaks_opt = []
            broken_opt = None

            # Verify if post-event shortest route contains cloud-covered edges
            path_opt = _reconstruct_path_to_dest(n_idx, dest_idx, nodes_list, pred_opt)
            has_cloud_opt = False
            for i in range(len(path_opt) - 2):  # exclude __DEST__
                e = G.get_edge_data(path_opt[i], path_opt[i + 1])
                if e and e.get("damage_grade") == "Unknown (cloud)":
                    has_cloud_opt = True
                    break

            if has_cloud_opt:
                status_opt = "connected (unverified: route passes cloud-covered segments)"
                connected_unverified_opt.append(s_id)
            else:
                status_opt = "connected (route verified clear)"
                connected_clear_opt.append(s_id)
        else:
            status_opt = "cut_off"
            post_dist_opt_km = None
            detour_opt_km = None
            breaks_opt = find_all_breaking_edges(G, path_from_s, blocked_grades={"Destroyed"})
            broken_opt = breaks_opt[0] if breaks_opt else None
            cut_off_optimistic.append({
                "settlement_id": s_id,
                "name": s_name,
                "building_count": b_count,
                "population": pop,
                "pre_route_km": pre_dist_km,
                "breaks": breaks_opt,
                "broken_element": broken_opt,
                "pre_path": path_from_s[:-1]  # drop __DEST__
            })

        # Pessimistic scenario
        can_pess = not np.isinf(dist_pess[n_idx])
        if can_pess:
            post_dist_pess_km = round(float(dist_pess[n_idx]) / 1000.0, 3)
            detour_pess_km = round(max(0.0, post_dist_pess_km - pre_dist_km), 3)
            breaks_pess = []
            broken_pess = None

            path_pess = _reconstruct_path_to_dest(n_idx, dest_idx, nodes_list, pred_pess)
            has_cloud_pess = False
            for i in range(len(path_pess) - 2):  # exclude __DEST__
                e = G.get_edge_data(path_pess[i], path_pess[i + 1])
                if e and e.get("damage_grade") == "Unknown (cloud)":
                    has_cloud_pess = True
                    break

            if has_cloud_pess:
                status_pess = "connected (unverified: route passes cloud-covered segments)"
                connected_unverified_pess.append(s_id)
            else:
                status_pess = "connected (route verified clear)"
                connected_clear_pess.append(s_id)
        else:
            status_pess = "cut_off"
            post_dist_pess_km = None
            detour_pess_km = None
            breaks_pess = find_all_breaking_edges(G, path_from_s, blocked_grades={"Destroyed", "Possibly damaged"})
            broken_pess = breaks_pess[0] if breaks_pess else None
            cut_off_pessimistic.append({
                "settlement_id": s_id,
                "name": s_name,
                "building_count": b_count,
                "population": pop,
                "pre_route_km": pre_dist_km,
                "breaks": breaks_pess,
                "broken_element": broken_pess,
                "pre_path": path_from_s[:-1]
            })

        s_results.append({
            "settlement_id": s_id,
            "name": s_name,
            "building_count": b_count,
            "population": pop,
            "snap_distance_m": round(float(d_snap), 1),
            "status_optimistic": status_opt,
            "status_pessimistic": status_pess,
            "pre_distance_km": pre_dist_km,
            "post_distance_opt_km": post_dist_opt_km,
            "post_distance_pess_km": post_dist_pess_km,
            "detour_opt_km": detour_opt_km,
            "detour_pess_km": detour_pess_km,
            "breaks_opt": breaks_opt,
            "breaks_pess": breaks_pess,
            "broken_element_opt": broken_opt,
            "broken_element_pess": broken_pess,
            "pre_path": path_from_s[:-1]
        })

    summary = {
        "network": network_name,
        "total_settlements": len(settlements_gdf),
        "valid_destinations_count": len(valid_d_nodes),
        "optimistic": {
            "cut_off_count": len(cut_off_optimistic),
            "connected_clear_count": len(connected_clear_opt),
            "connected_unverified_count": len(connected_unverified_opt),
            "connected_total_count": len(connected_clear_opt) + len(connected_unverified_opt),
            "no_access_count": len(no_access_list),
            "cut_off_settlements": cut_off_optimistic,
            "connected_clear_settlements": connected_clear_opt,
            "connected_unverified_settlements": connected_unverified_opt
        },
        "pessimistic": {
            "cut_off_count": len(cut_off_pessimistic),
            "connected_clear_count": len(connected_clear_pess),
            "connected_unverified_count": len(connected_unverified_pess),
            "connected_total_count": len(connected_clear_pess) + len(connected_unverified_pess),
            "no_access_count": len(no_access_list),
            "cut_off_settlements": cut_off_pessimistic,
            "connected_clear_settlements": connected_clear_pess,
            "connected_unverified_settlements": connected_unverified_pess
        },
        "settlement_details": s_results
    }

    return summary
