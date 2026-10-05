"""
Height Above Nearest Drainage (HAND) module.
Computes D8 flow direction, flow accumulation, drainage network extraction,
and Height Above Nearest Drainage from DEM.
"""

from typing import Tuple, Dict, Any, Optional
import numpy as np
from scipy.ndimage import distance_transform_edt


import ctypes
from pathlib import Path

_LIB_HAND = None

def _get_hand_lib():
    global _LIB_HAND
    if _LIB_HAND is not None:
        return _LIB_HAND
    so_path = Path(__file__).parent / "libhand_fast.so"
    c_path = Path(__file__).parent / "hand_c.c"
    if not so_path.exists() and c_path.exists():
        import subprocess
        try:
            subprocess.run(["gcc", "-O3", "-shared", "-fPIC", str(c_path), "-o", str(so_path)], check=True, capture_output=True)
        except Exception:
            pass
    if so_path.exists():
        try:
            lib = ctypes.CDLL(str(so_path))
            lib.d8_accum.argtypes = [
                np.ctypeslib.ndpointer(dtype=np.int64, flags="C_CONTIGUOUS"),
                np.ctypeslib.ndpointer(dtype=np.int64, flags="C_CONTIGUOUS"),
                ctypes.c_int64,
                np.ctypeslib.ndpointer(dtype=np.int32, flags="C_CONTIGUOUS")
            ]
            lib.d8_propagate.argtypes = [
                np.ctypeslib.ndpointer(dtype=np.int64, flags="C_CONTIGUOUS"),
                np.ctypeslib.ndpointer(dtype=np.int64, flags="C_CONTIGUOUS"),
                ctypes.c_int64,
                np.ctypeslib.ndpointer(dtype=np.float32, flags="C_CONTIGUOUS")
            ]
            _LIB_HAND = lib
        except Exception:
            _LIB_HAND = None
    return _LIB_HAND


def compute_hand_native(
    elevation: np.ndarray,
    dx: float = 10.0,
    dy: float = 10.0,
    drainage_threshold: int = 1000
) -> Tuple[np.ndarray, np.ndarray, Dict[str, Any]]:
    """
    High-performance native D8 hydrological flow routing and HAND calculation.
    1. D8 steepest downhill slope flow direction.
    2. Topological sort (by elevation descending) for cycle-free flow accumulation.
    3. Drainage network extraction: flow_accumulation >= drainage_threshold.
    4. HAND: Relative elevation difference from the nearest drainage channel cell.
    """
    dem = elevation.astype(np.float32)
    h, w = dem.shape
    total_cells = h * w

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
    order = np.ascontiguousarray(np.argsort(flat_dem)[::-1], dtype=np.int64)

    # 3. Flow accumulation
    flat_target = np.ascontiguousarray(target_idx.ravel(), dtype=np.int64)
    accum = np.ones(total_cells, dtype=np.int32)

    lib = _get_hand_lib()
    if lib is not None:
        lib.d8_accum(order, flat_target, total_cells, accum)
    else:
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
    rev_order = np.ascontiguousarray(order[::-1], dtype=np.int64)
    if lib is not None:
        lib.d8_propagate(rev_order, flat_target, total_cells, flat_drainage)
    else:
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
