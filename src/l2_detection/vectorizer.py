"""
Polygon vectorization and Douglas-Peucker boundary smoothing module.
"""

import os
import json
from typing import Dict, Any, List
import numpy as np
import rasterio
from rasterio.features import shapes
from shapely.geometry import shape, mapping, MultiPolygon, Polygon
import pyproj
from shapely.ops import transform

CLASS_NAMES = {
    1: "Permanent Water",
    2: "Flood / Debris Affected",
    3: "Inferred Flooded"
}


def vectorize_hazard_classes(
    hazard_raster: np.ndarray,
    transform_matrix: Any,
    crs: Any,
    out_geojson_path: str,
    simplify_tolerance_m: float = 8.0,
    min_area_m2: float = 500.0,
    channel_affected_mask: Any = None,
    builtup_affected_mask: Any = None,
    default_c2_sublabel: str = "valley"
) -> Dict[str, Any]:
    """
    Vectorize 2D hazard classification raster into simplified GeoJSON polygons.
    Simplifies geometry via Douglas-Peucker to eliminate raster staircasing.
    Assigns sub_label ('channel', 'built-up', or 'valley') to class 2 polygons.
    """
    os.makedirs(os.path.dirname(os.path.abspath(out_geojson_path)), exist_ok=True)

    # Setup reprojector to WGS84 for GeoJSON standards
    is_projected = crs.is_projected if crs else True
    if is_projected and str(crs) != "EPSG:4326":
        to_wgs84 = pyproj.Transformer.from_crs(crs, "EPSG:4326", always_xy=True).transform
    else:
        to_wgs84 = None

    features = []
    class_areas_m2 = {1: 0.0, 2: 0.0, 3: 0.0}

    # Extract polygon contours for each hazard class
    for class_id in [1, 2, 3]:
        class_mask = (hazard_raster == class_id).astype(np.uint8)
        if np.sum(class_mask) == 0:
            continue

        raw_shapes = shapes(class_mask, mask=(class_mask == 1), transform=transform_matrix)
        for geom_dict, val in raw_shapes:
            poly = shape(geom_dict)
            if not poly.is_valid:
                poly = poly.buffer(0)

            # Metric area in square meters
            area_m2 = float(poly.area)
            if area_m2 < min_area_m2:
                continue

            class_areas_m2[class_id] += area_m2

            # Determine sub-label (channel vs built-up vs valley vs flood water)
            sub_label = default_c2_sublabel if class_id == 2 else ("river" if class_id == 1 else "inferred")
            if class_id == 2:
                minx, miny, maxx, maxy = poly.bounds
                inv_trans = ~transform_matrix
                c1, r2 = inv_trans * (minx, miny)
                c2, r1 = inv_trans * (maxx, maxy)
                r_start = max(0, int(np.floor(min(r1, r2))))
                r_end = min(hazard_raster.shape[0], int(np.ceil(max(r1, r2))))
                c_start = max(0, int(np.floor(min(c1, c2))))
                c_end = min(hazard_raster.shape[1], int(np.ceil(max(c1, c2))))
                if builtup_affected_mask is not None and np.any(builtup_affected_mask[r_start:r_end, c_start:c_end] == 1):
                    sub_label = "built-up"
                elif channel_affected_mask is not None and np.any(channel_affected_mask[r_start:r_end, c_start:c_end] == 1):
                    sub_label = "channel"

            # Smooth polygon edges to eliminate staircase artifacts
            smoothed_poly = poly.simplify(tolerance=simplify_tolerance_m, preserve_topology=True)
            if not smoothed_poly.is_valid:
                smoothed_poly = smoothed_poly.buffer(0)

            # Convert to WGS84 coordinates for GeoJSON export
            if to_wgs84:
                wgs_geom = transform(to_wgs84, smoothed_poly)
            else:
                wgs_geom = smoothed_poly

            feature = {
                "type": "Feature",
                "geometry": mapping(wgs_geom),
                "properties": {
                    "class": int(class_id),
                    "class_name": CLASS_NAMES.get(class_id, "Unknown"),
                    "sub_label": sub_label,
                    "area_m2": round(area_m2, 1),
                    "area_km2": round(area_m2 / 1e6, 5)
                }
            }
            features.append(feature)

    geojson_doc = {
        "type": "FeatureCollection",
        "crs": {
            "type": "name",
            "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"}
        },
        "features": features
    }

    with open(out_geojson_path, "w") as f:
        json.dump(geojson_doc, f, indent=2)

    return {
        "total_polygons": len(features),
        "class_areas_m2": class_areas_m2,
        "class_areas_km2": {k: round(v / 1e6, 4) for k, v in class_areas_m2.items()},
        "output_path": out_geojson_path
    }
