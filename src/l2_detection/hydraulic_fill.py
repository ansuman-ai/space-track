"""
Hydraulic flood corridor inference via reach-based HAND stage filling.
Divides drainage network into reaches of length L, computes local flood stage
from touching observed flood/debris pixels (P-th percentile of HAND), and
performs hydrologically connected flood-filling.
"""

from typing import Dict, Any, Tuple, Optional
import numpy as np
import networkx as nx
from scipy.ndimage import distance_transform_edt, label


def segment_stream_reaches(
    stream_mask: np.ndarray,
    pixel_size_m: float = 10.0,
    reach_length_m: float = 250.0
) -> Tuple[np.ndarray, np.ndarray, int]:
    """
    Splits drainage channel network into reaches of length reach_length_m (default 250 m).
    Returns:
    - reach_map: 2D array of reach IDs on stream pixels
    - nearest_reach: 2D array mapping every grid cell to its nearest reach ID
    - total_reaches: total number of reaches created
    """
    h, w = stream_mask.shape
    L_cells = max(1, int(round(reach_length_m / pixel_size_m)))

    G = nx.Graph()
    rows, cols = np.where(stream_mask == 1)
    cell_set = set(zip(rows, cols))

    for r, c in cell_set:
        G.add_node((r, c))
        for dr in [-1, 0, 1]:
            for dc in [-1, 0, 1]:
                if dr == 0 and dc == 0:
                    continue
                nbr = (r + dr, c + dc)
                if nbr in cell_set:
                    G.add_edge((r, c), nbr)

    reach_map = np.zeros((h, w), dtype=np.int32)
    reach_id = 1

    for comp in nx.connected_components(G):
        subG = G.subgraph(comp)
        endpoints = [n for n in subG.nodes() if subG.degree(n) == 1]
        start_node = endpoints[0] if endpoints else list(subG.nodes())[0]

        visited = set()
        queue = [start_node]
        ordered = []
        while queue:
            curr = queue.pop(0)
            if curr in visited:
                continue
            visited.add(curr)
            ordered.append(curr)
            for nbr in subG.neighbors(curr):
                if nbr not in visited:
                    queue.append(nbr)

        for i in range(0, len(ordered), L_cells):
            for r, c in ordered[i:i + L_cells]:
                reach_map[r, c] = reach_id
            reach_id += 1

    total_reaches = reach_id - 1
    _, (nr_r, nr_c) = distance_transform_edt(reach_map == 0, return_indices=True)
    nearest_reach = reach_map[nr_r, nr_c]

    return reach_map, nearest_reach, total_reaches


def compute_inferred_flood_corridor(
    hand: np.ndarray,
    stream_mask: np.ndarray,
    observed_class2_mask: np.ndarray,
    pixel_size_m: float = 10.0,
    reach_length_m: float = 250.0,
    hand_percentile: float = 90.0,
    min_observed_pixels: int = 20,
    touch_distance_m: float = 100.0,
    max_hand_corridor_m: float = 40.0
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """
    Inferred flood corridor (HAND-based fill):
    1. Splits drainage network into reaches of reach_length_m.
    2. Takes HAND values of observed class 2 pixels touching each reach; flood level = percentile.
    3. Flood fills hydrologically connected cells with HAND <= flood level.
    """
    h, w = hand.shape
    reach_map, nearest_reach, total_reaches = segment_stream_reaches(
        stream_mask=stream_mask,
        pixel_size_m=pixel_size_m,
        reach_length_m=reach_length_m
    )

    dist_to_stream = distance_transform_edt(stream_mask == 0) * pixel_size_m
    touching_observed = observed_class2_mask & (dist_to_stream <= touch_distance_m) & (hand <= max_hand_corridor_m)

    inferred_mask = np.zeros((h, w), dtype=bool)
    active_reaches = 0
    reach_stages = {}

    for rid in range(1, total_reaches + 1):
        reach_cells = (reach_map == rid)
        mask_r = touching_observed & (nearest_reach == rid)
        n_obs = int(np.sum(mask_r))
        if n_obs < min_observed_pixels:
            continue

        active_reaches += 1
        h_flood = float(np.percentile(hand[mask_r], hand_percentile))
        reach_stages[rid] = h_flood

        # Sub-region belonging to this reach with HAND <= h_flood
        cand = (nearest_reach == rid) & (hand <= h_flood) & (hand >= 0)
        lbl, num = label(cand, structure=np.ones((3, 3)))
        touching_lbls = np.unique(lbl[reach_cells])
        touching_lbls = touching_lbls[touching_lbls > 0]
        inferred_mask |= np.isin(lbl, touching_lbls)

    # Do not overwrite class 2
    inferred_clean = inferred_mask & (~observed_class2_mask)
    pixel_area_km2 = (pixel_size_m ** 2) / 1e6

    stats = {
        "total_reaches": total_reaches,
        "active_reaches": active_reaches,
        "inferred_pixels": int(np.sum(inferred_clean)),
        "inferred_km2": round(float(np.sum(inferred_clean) * pixel_area_km2), 4),
        "mean_flood_stage_m": round(float(np.mean(list(reach_stages.values()))), 2) if reach_stages else 0.0
    }

    return inferred_clean, stats
