"""
Debris flow, sediment deposition, and gravel scouring detection module for Layer 2.
Class 3: Debris / Sediment.
"""

from typing import Tuple, Dict, Any, Optional
import numpy as np
from scipy.ndimage import uniform_filter, binary_dilation, label

from .thresholds import get_adaptive_debris_threshold


def filter_connected_to_channel(
    candidate_mask: np.ndarray,
    river_mask: np.ndarray,
    dilation_pixels: int = 8,
    min_pixels: int = 15
) -> np.ndarray:
    """
    Keep only candidate blobs connected or adjacent to the active drainage corridor,
    with area >= min_pixels.
    """
    if np.sum(candidate_mask) == 0:
        return np.zeros_like(candidate_mask, dtype=np.uint8)

    channel_influence = binary_dilation(river_mask, iterations=dilation_pixels)

    labeled, num_features = label(candidate_mask)
    if num_features == 0:
        return np.zeros_like(candidate_mask, dtype=np.uint8)

    counts = np.bincount(labeled.ravel())
    retained_mask = np.zeros_like(candidate_mask, dtype=np.uint8)

    for feat_id in range(1, num_features + 1):
        if counts[feat_id] < min_pixels:
            continue
        blob = (labeled == feat_id)
        if np.any(blob & channel_influence):
            retained_mask[blob] = 1

    return retained_mask


def detect_debris(
    log_ratio_vv: np.ndarray,
    log_ratio_vh: np.ndarray,
    pre_vv: np.ndarray,
    post_vv: np.ndarray,
    hand: np.ndarray,
    slope: np.ndarray,
    permanent_water_mask: np.ndarray,
    new_flood_mask: np.ndarray,
    shadow_mask: np.ndarray,
    max_hand_m: float = 40.0,
    min_slope_deg: float = 6.0,
    max_slope_deg: float = 35.0,
    t_rise_vv_db: float = 3.0,
    min_post_vv_db: float = -9.0,
    dilation_pixels: int = 8,
    min_pixels: int = 15
) -> Tuple[np.ndarray, Dict[str, float]]:
    """
    Detect debris/sediment deposits:
    - Significant backscatter surge in VV (rough angular rock scattering)
    - High absolute post-event backscatter (rough gravel deposit)
    - Constrained to HAND valley corridor and transport slopes
    - Not shadow/layover, not permanent water, not flood water
    - Connected or adjacent to the river channel
    - Above minimum area threshold
    """
    # Radiometric backscatter surge with rough surface response
    sar_surge = (log_ratio_vv >= t_rise_vv_db) & (post_vv >= min_post_vv_db)

    # Terrain corridor constraint
    terrain_corridor = (
        (hand <= max_hand_m) &
        (slope >= min_slope_deg) &
        (slope <= max_slope_deg) &
        (shadow_mask == 0) &
        (permanent_water_mask == 0) &
        (new_flood_mask == 0)
    )

    candidate = sar_surge & terrain_corridor

    # River channel connectivity filter
    combined_water = (permanent_water_mask | new_flood_mask).astype(np.uint8)
    debris_clean = filter_connected_to_channel(
        candidate_mask=candidate,
        river_mask=combined_water,
        dilation_pixels=dilation_pixels,
        min_pixels=min_pixels
    )

    # Mutual exclusivity
    debris_clean[permanent_water_mask == 1] = 0
    debris_clean[new_flood_mask == 1] = 0

    thresholds = {
        "t_debris_rise_vv_db": float(t_rise_vv_db),
        "min_post_vv_debris_db": float(min_post_vv_db),
        "max_hand_debris_m": float(max_hand_m),
        "min_slope_debris_deg": float(min_slope_deg),
        "max_slope_debris_deg": float(max_slope_deg)
    }

    return debris_clean, thresholds
