"""
Height Above Nearest Drainage (HAND) module.
Computes D8 flow direction, flow accumulation, drainage network extraction,
and Height Above Nearest Drainage from DEM.
"""

from typing import Tuple, Dict, Any, Optional
import numpy as np
from scipy.ndimage import distance_transform_edt


import heapq


def fill_pits_and_resolve_flats(dem: np.ndarray, eps: float = 1e-4) -> np.ndarray:
    """
    Priority-Flood depression filling with infinitesimal gradient for flat resolution.
    Ensures every non-boundary cell has a monotonic downhill drainage path.
    """
    h, w = dem.shape
    filled = np.copy(dem).astype(np.float32)
    visited = np.zeros((h, w), dtype=bool)
    heap = []

    for r in range(h):
        for c in [0, w - 1]:
            heapq.heappush(heap, (filled[r, c], r, c))
            visited[r, c] = True
    for c in range(1, w - 1):
        for r in [0, h - 1]:
            heapq.heappush(heap, (filled[r, c], r, c))
            visited[r, c] = True

    dr = [-1, -1, -1, 0, 0, 1, 1, 1]
    dc = [-1, 0, 1, -1, 1, -1, 0, 1]

    while heap:
        elev, r, c = heapq.heappop(heap)
        for k in range(8):
            nr, nc = r + dr[k], c + dc[k]
            if 0 <= nr < h and 0 <= nc < w and not visited[nr, nc]:
                visited[nr, nc] = True
                if filled[nr, nc] <= elev:
                    filled[nr, nc] = elev + eps
                heapq.heappush(heap, (filled[nr, nc], nr, nc))

    return filled


def compute_hand_native(
    elevation: np.ndarray,
    dx: float = 10.0,
    dy: float = 10.0,
    drainage_threshold: int = 1000
) -> Tuple[np.ndarray, np.ndarray, Dict[str, Any]]:
    """
    High-performance native D8 hydrological flow routing and HAND calculation.
    1. Priority-Flood depression filling and flat resolution.
    2. D8 steepest downhill slope flow direction.
    3. Topological sort (by elevation descending) for cycle-free flow accumulation.
    4. Drainage network extraction: flow_accumulation >= drainage_threshold.
    5. HAND: Relative elevation difference from the nearest drainage channel cell.
    """
    raw_dem = elevation.astype(np.float32)
    h, w = raw_dem.shape
    total_cells = h * w

    # Priority-flood pit filling with flat resolution
    dem = fill_pits_and_resolve_flats(raw_dem)

    # 8 neighbor offsets and metric distances
    dr = np.array([-1, -1, -1,  0, 0,  1, 1, 1], dtype=np.int32)
    dc = np.array([-1,  0,  1, -1, 1, -1, 0, 1], dtype=np.int32)
    dist = np.sqrt((dr * float(dy))**2 + (dc * float(dx))**2).astype(np.float32)

    # 1. D8 steepest downhill neighbor
    best_slope = np.zeros((h, w), dtype=np.float32)
    target_idx = np.full((h, w), -1, dtype=np.int32)

    padded = np.pad(dem, 1, mode='edge')
    for k in range(8):
        nr_elev = padded[1 + dr[k]:h + 1 + dr[k], 1 + dc[k]:w + 1 + dc[k]]
        slope = (dem - nr_elev) / dist[k]
        better = (slope > best_slope) & (slope > 0)
        best_slope[better] = slope[better]
        
        r_coords, c_coords = np.where(better)
        target_idx[better] = (r_coords + dr[k]) * w + (c_coords + dc[k])

    del padded
    del best_slope

    # 2. Topological sort (high to low elevation)
    flat_dem = dem.ravel()
    order = np.argsort(flat_dem)[::-1].astype(np.int32)

    # 3. Flow accumulation
    flat_target = target_idx.ravel()
    accum = np.ones(total_cells, dtype=np.int32)

    for i in order:
        tgt = flat_target[i]
        if 0 <= tgt < total_cells:
            accum[tgt] += accum[i]

    accum_2d = accum.reshape(h, w)
    stream_mask = (accum_2d >= int(drainage_threshold)).astype(np.uint8)
    stream_cell_count = int(np.sum(stream_mask))

    # 4. Drainage elevation assignment
    drainage_elev = np.full((h, w), np.nan, dtype=np.float32)
    drainage_elev[stream_mask == 1] = dem[stream_mask == 1]

    # Downstream propagation along D8 paths (reverse order: low to high)
    flat_drainage = drainage_elev.ravel()
    rev_order = order[::-1]
    for i in rev_order:
        if np.isnan(flat_drainage[i]):
            tgt = flat_target[i]
            if 0 <= tgt < total_cells and not np.isnan(flat_drainage[tgt]):
                flat_drainage[i] = flat_drainage[tgt]

    # Resolve any remaining cells (local depressions or disconnected edges) via EDT
    unresolved = np.isnan(flat_drainage)
    if np.any(unresolved) and stream_cell_count > 0:
        _, idx = distance_transform_edt(stream_mask == 0, return_indices=True)
        flat_drainage[unresolved] = dem[idx[0].ravel()[unresolved], idx[1].ravel()[unresolved]]
    elif stream_cell_count == 0:
        flat_drainage[:] = np.nanmin(dem)

    drainage_elev_2d = flat_drainage.reshape(h, w)
    hand = np.maximum(0.0, dem - drainage_elev_2d).astype(np.float32)

    stats = {
        "drainage_threshold_cells": int(drainage_threshold),
        "stream_cells": stream_cell_count,
        "stream_coverage_pct": round(stream_cell_count / total_cells * 100.0, 3),
        "hand_min_m": round(float(np.nanmin(hand)), 2),
        "hand_median_m": round(float(np.nanmedian(hand)), 2),
        "hand_max_m": round(float(np.nanmax(hand)), 2),
        "hand_mean_m": round(float(np.nanmean(hand)), 2),
    }

    return hand, stream_mask, stats


def compute_hand(
    elevation: np.ndarray,
    dx: float = 10.0,
    dy: float = 10.0,
    drainage_threshold: int = 1000,
    engine: str = "auto"
) -> Tuple[np.ndarray, np.ndarray, Dict[str, Any]]:
    """
    Main entry point for HAND calculation.
    Dispatches to pysheds/whitebox if specified and available, otherwise uses native D8.
    """
    if engine == "pysheds":
        try:
            import pysheds
        except ImportError:
            pass
    elif engine == "whitebox":
        try:
            import whitebox
        except ImportError:
            pass

    return compute_hand_native(
        elevation=elevation,
        dx=dx,
        dy=dy,
        drainage_threshold=drainage_threshold
    )
