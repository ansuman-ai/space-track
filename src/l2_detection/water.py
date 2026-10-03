"""
Permanent water and new flood water detection modules for Layer 2.
Classes:
  1: Permanent Water (baseline pre-event channel)
  2: New Flood Water (inundation expansion)
"""

import os
from typing import Tuple, Dict, Any, Optional
import numpy as np
import rasterio
from rasterio.features import rasterize
import geopandas as gpd
from scipy.ndimage import binary_opening, binary_closing, label, generate_binary_structure

from .thresholds import get_adaptive_water_threshold, get_adaptive_delta_flood_threshold


def filter_min_blob_size(mask: np.ndarray, min_pixels: int = 10) -> np.ndarray:
    """
    Remove connected component blobs smaller than min_pixels.
    """
    labeled, num_features = label(mask)
    if num_features == 0:
        return mask.astype(np.uint8)

    counts = np.bincount(labeled.ravel())
    remove_mask = counts < min_pixels
    remove_mask[0] = False  # Keep background
    mask_clean = mask.copy()
    mask_clean[remove_mask[labeled]] = 0
    return mask_clean.astype(np.uint8)


def detect_permanent_water(
    pre_vv: np.ndarray,
    hand: np.ndarray,
    shadow_mask: np.ndarray,
    osm_waterways_path: str,
    transform_matrix: Any,
    crs: Any,
    hand_corridor_m: float = 15.0,
    osm_buffer_m: float = 15.0,
    min_pixels: int = 10,
    pre_ndwi: Optional[np.ndarray] = None
) -> Tuple[np.ndarray, float]:
    """
    Detect permanent water:
    Pre-event NDWI (> 0) + OSM waterways, constrained to active valley floor (hand <= 15m).
    Falls back to SAR pre-event VV if pre_ndwi is not supplied.
    """
    t_otsu = 0.0
    if pre_ndwi is not None:
        base_perm = (pre_ndwi > 0.0) & (hand <= hand_corridor_m)
    else:
        t_otsu = get_adaptive_water_threshold(
            pre_vv=pre_vv,
            hand=hand,
            shadow_mask=shadow_mask,
            hand_corridor_m=hand_corridor_m
        )
        base_perm = (pre_vv <= t_otsu) & (hand <= hand_corridor_m) & (shadow_mask == 0)

    # OSM waterways vector support
    osm_perm = np.zeros_like(base_perm, dtype=bool)
    if os.path.exists(osm_waterways_path):
        try:
            gdf = gpd.read_file(osm_waterways_path)
            if not gdf.empty:
                if gdf.crs != crs:
                    gdf = gdf.to_crs(crs)

                # Separate true linestrings from bounding box polygons
                lines = gdf[gdf.geometry.geom_type.isin(["LineString", "MultiLineString"])]
                polys = gdf[gdf.geometry.geom_type.isin(["Polygon", "MultiPolygon"])]

                if not lines.empty:
                    buf_lines = [geom.buffer(osm_buffer_m) for geom in lines.geometry if geom is not None and not geom.is_empty]
                    line_mask = rasterize([(g, 1) for g in buf_lines], out_shape=pre_vv.shape, transform=transform_matrix, fill=0, dtype=np.uint8)
                    osm_perm |= (line_mask == 1) & (hand <= hand_corridor_m)
        except Exception:
            pass

    combined = (base_perm | osm_perm).astype(np.uint8)

    # Morphological clean
    combined = binary_opening(combined, structure=np.ones((3, 3))).astype(np.uint8)
    combined = filter_min_blob_size(combined, min_pixels=min_pixels)

    return combined, t_otsu


def detect_new_flood_water(
    post_vv: np.ndarray,
    log_ratio_vv: np.ndarray,
    hand: np.ndarray,
    slope: np.ndarray,
    permanent_water_mask: np.ndarray,
    shadow_mask: np.ndarray,
    max_hand_m: float = 20.0,
    max_slope_deg: float = 12.0,
    min_pixels: int = 8
) -> Tuple[np.ndarray, float, float]:
    """
    Detect new flood water:
    Low post VV AND log-ratio VV decrease (adaptive threshold),
    NOT permanent water, NOT shadow/layover, HAND below config value, low slope.
    """
    t_post_water = get_adaptive_water_threshold(
        pre_vv=post_vv,
        hand=hand,
        shadow_mask=shadow_mask,
        hand_corridor_m=max_hand_m
    )

    candidate_specular = (post_vv <= t_post_water) & (shadow_mask == 0) & (hand <= max_hand_m)
    t_delta_flood = get_adaptive_delta_flood_threshold(
        log_ratio_vv=log_ratio_vv,
        candidate_mask=candidate_specular,
        default_threshold=-2.8
    )

    flood_raw = (
        (post_vv <= t_post_water) &
        (log_ratio_vv <= t_delta_flood) &
        (permanent_water_mask == 0) &
        (shadow_mask == 0) &
        (hand <= max_hand_m) &
        (slope <= max_slope_deg)
    ).astype(np.uint8)

    cross = generate_binary_structure(2, 1)
    flood_closed = binary_closing(flood_raw, structure=cross).astype(np.uint8)
    flood_clean = filter_min_blob_size(flood_closed, min_pixels=min_pixels)

    # Strictly mutually exclusive
    flood_clean[permanent_water_mask == 1] = 0

    return flood_clean, t_post_water, t_delta_flood

