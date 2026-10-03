"""
Grid verification and reprojection/resampling module.
"""

from typing import Tuple, Dict, Any, Optional
import numpy as np
import rasterio
from rasterio.warp import reproject, Resampling


def check_grid_identity(
    src_a: rasterio.io.DatasetReader,
    src_b: rasterio.io.DatasetReader,
    transform_tol: float = 1e-4
) -> Tuple[bool, Dict[str, Any]]:
    """
    Check if two raster datasets share identical CRS, transform, and shape.
    """
    crs_match = (src_a.crs == src_b.crs)
    shape_match = (src_a.shape == src_b.shape)

    t_a = src_a.transform
    t_b = src_b.transform
    transform_match = all(abs(a - b) <= transform_tol for a, b in zip(t_a, t_b))

    is_identical = crs_match and shape_match and transform_match
    details = {
        "is_identical": is_identical,
        "crs_match": crs_match,
        "shape_match": shape_match,
        "transform_match": transform_match,
        "crs_a": str(src_a.crs),
        "crs_b": str(src_b.crs),
        "shape_a": src_a.shape,
        "shape_b": src_b.shape,
    }
    return is_identical, details


def align_raster_to_reference(
    src_path: str,
    ref_profile: Dict[str, Any],
    resampling: Resampling = Resampling.bilinear,
    num_threads: int = 2
) -> np.ndarray:
    """
    Reproject and resample an input raster onto a reference grid.
    Returns:
        dst_array (bands, height, width) in float32.
    """
    with rasterio.open(src_path) as src:
        count = src.count
        height = ref_profile["height"]
        width = ref_profile["width"]
        dst_crs = ref_profile["crs"]
        dst_transform = ref_profile["transform"]

        dst_array = np.zeros((count, height, width), dtype=np.float32)

        for b in range(1, count + 1):
            reproject(
                source=rasterio.band(src, b),
                destination=dst_array[b - 1],
                src_transform=src.transform,
                src_crs=src.crs,
                dst_transform=dst_transform,
                dst_crs=dst_crs,
                resampling=resampling,
                num_threads=num_threads
            )

    return dst_array


def resample_dem_to_grid(
    dem_path: str,
    ref_profile: Dict[str, Any],
    resampling: Resampling = Resampling.bilinear
) -> np.ndarray:
    """
    Resample DEM to reference raster grid (e.g., S1 grid) using bilinear interpolation.
    Returns 2D float32 elevation array.
    """
    aligned = align_raster_to_reference(dem_path, ref_profile, resampling=resampling)
    return aligned[0]
