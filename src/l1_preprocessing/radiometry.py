"""
Radiometric check, unclipped dB conversion, and log-ratio computation.
"""

from typing import Tuple, Dict, Any, Optional
import numpy as np


def check_and_convert_to_db(
    array: np.ndarray,
    nodata: Optional[float] = None,
    eps: float = 1e-7
) -> Tuple[np.ndarray, bool, Dict[str, float]]:
    """
    Check whether array is in linear power or decibels (dB).
    If values are linear power, convert to dB without artificial clipping.
    sigma0_db = 10 * log10(max(linear, eps))
    Returns:
        (array_db, converted_bool, stats_dict)
    """
    valid_mask = np.isfinite(array)
    if nodata is not None:
        valid_mask &= (array != nodata)
    valid_mask &= (array > 0.0)

    valid_vals = array[valid_mask]
    if valid_vals.size == 0:
        return array.astype(np.float32), False, {"min": 0.0, "median": 0.0, "max": 0.0, "mean": 0.0}

    # If 5th percentile is negative or median < 0, data is already in dB
    p5 = float(np.percentile(valid_vals, 5))
    median_val = float(np.median(valid_vals))
    min_val = float(np.min(valid_vals))

    is_already_db = (min_val < 0.0) or (p5 < 0.0) or (median_val < 0.0)

    if is_already_db:
        array_db = array.astype(np.float32)
        converted = False
    else:
        # Values are linear power: strictly convert without artificial clipping
        array_db = np.full(array.shape, np.nan, dtype=np.float32)
        array_db[valid_mask] = (10.0 * np.log10(np.maximum(valid_vals, eps))).astype(np.float32)
        converted = True

    # Recompute stats on valid dB values
    valid_db = array_db[np.isfinite(array_db)]
    stats = {
        "min": float(np.min(valid_db)),
        "median": float(np.median(valid_db)),
        "max": float(np.max(valid_db)),
        "mean": float(np.mean(valid_db)),
    }

    return array_db, converted, stats


def compute_log_ratio(
    post_db: np.ndarray,
    pre_db: np.ndarray,
    nodata_mask: Optional[np.ndarray] = None
) -> np.ndarray:
    """
    Compute log-ratio difference in dB: post_dB - pre_dB.
    Equivalent to 10 * log10(post_linear / pre_linear).
    """
    log_ratio = post_db.astype(np.float32) - pre_db.astype(np.float32)
    if nodata_mask is not None:
        log_ratio[nodata_mask] = np.nan
    return log_ratio
