"""
Lee speckle filtering for SAR imagery.
"""

from typing import Optional
import numpy as np
from scipy.ndimage import uniform_filter


def apply_lee_filter(
    img: np.ndarray,
    window_size: int = 5,
    damping_factor: float = 1.0
) -> np.ndarray:
    """
    Standard adaptive Lee speckle filter (window_size x window_size).
    Filters homogeneous regions while preserving structural boundaries and edges.
    Operates in float32.
    """
    if window_size % 2 == 0:
        window_size += 1

    img_f32 = img.astype(np.float32)
    nan_mask = ~np.isfinite(img_f32)

    if np.any(nan_mask):
        valid_median = float(np.nanmedian(img_f32))
        img_work = np.where(nan_mask, valid_median, img_f32)
    else:
        img_work = img_f32

    img_mean = uniform_filter(img_work, size=window_size)
    img_sqr_mean = uniform_filter(img_work ** 2, size=window_size)
    img_variance = np.maximum(img_sqr_mean - img_mean ** 2, 0.0)

    overall_variance = float(np.var(img_work))
    if overall_variance <= 1e-7:
        return img_f32

    weight = img_variance / (img_variance + (overall_variance / damping_factor) + 1e-7)
    weight = np.clip(weight, 0.0, 1.0)

    filtered = img_mean + weight * (img_work - img_mean)

    if np.any(nan_mask):
        filtered[nan_mask] = np.nan

    return filtered.astype(np.float32)
