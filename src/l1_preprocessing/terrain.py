"""
Terrain analysis module: Slope, Aspect, and SAR Layover/Shadow Masking.
"""

from typing import Tuple, Dict, Any
import numpy as np
from scipy.ndimage import sobel


def compute_slope_aspect(
    elevation: np.ndarray,
    dx: float,
    dy: float
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Compute terrain slope (degrees) and aspect (degrees clockwise from North)
    from elevation raster using 2D Sobel spatial gradients.
    """
    elev_f32 = elevation.astype(np.float32)

    # Gradient in Y (North-South) and X (East-West)
    dz_dy = sobel(elev_f32, axis=0) / (8.0 * float(dy))
    dz_dx = sobel(elev_f32, axis=1) / (8.0 * float(dx))

    # Slope in degrees [0, 90]
    slope_rad = np.arctan(np.sqrt(dz_dx**2 + dz_dy**2))
    slope_deg = np.clip(np.rad2deg(slope_rad), 0.0, 90.0).astype(np.float32)

    # Aspect in degrees [0, 360) clockwise from North (0=North, 90=East, 180=South, 270=West)
    aspect_rad = np.arctan2(-dz_dx, dz_dy)
    aspect_deg = (np.rad2deg(aspect_rad) % 360.0).astype(np.float32)

    return slope_deg, aspect_deg


def compute_shadow_layover_mask(
    slope_deg: np.ndarray,
    aspect_deg: np.ndarray,
    look_angle_deg: float = 38.0,
    orbit_heading_deg: float = 350.0
) -> Tuple[np.ndarray, Dict[str, float]]:
    """
    Compute SAR layover and radar shadow mask based on terrain slope, aspect,
    and radar sensor look geometry.
    - Right-looking sensor: look direction = (orbit_heading + 90) % 360.
    - Layover occurs when terrain slope facing towards the radar antenna >= look angle.
    - Shadow occurs when terrain slope tilting away from radar >= 90 - look angle.
    Returns:
        (mask_uint8, stats_dict)
    """
    look_direction_deg = (float(orbit_heading_deg) + 90.0) % 360.0

    rel_aspect = np.abs(aspect_deg - look_direction_deg)
    rel_aspect = np.where(rel_aspect > 180.0, 360.0 - rel_aspect, rel_aspect)

    slope_in_range = slope_deg * np.cos(np.deg2rad(rel_aspect))

    layover = slope_in_range >= float(look_angle_deg)
    shadow = slope_in_range <= -(90.0 - float(look_angle_deg))

    mask = (layover | shadow).astype(np.uint8)

    total_cells = mask.size
    pct_layover = float(np.sum(layover) / total_cells * 100.0)
    pct_shadow = float(np.sum(shadow) / total_cells * 100.0)
    pct_total = float(np.sum(mask) / total_cells * 100.0)

    stats = {
        "pct_layover": round(pct_layover, 2),
        "pct_shadow": round(pct_shadow, 2),
        "pct_masked": round(pct_total, 2),
        "look_angle_deg": float(look_angle_deg),
        "orbit_heading_deg": float(orbit_heading_deg),
        "look_direction_deg": float(look_direction_deg),
    }

    return mask, stats
