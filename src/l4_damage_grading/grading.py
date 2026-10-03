"""
Critical Infrastructure Damage Grading Engine.
Applies EMS-style damage classification to buildings, roads, and bridges
conditioned on Layer 2 flood hazard polygons (Class 2: Observed, Class 3: Inferred)
and cloud/nodata validity masks.
"""

from typing import Dict, Any, Tuple, List, Optional
import numpy as np
import geopandas as gpd
from shapely.geometry import LineString, MultiLineString, Polygon, MultiPolygon
from shapely.ops import substring


def check_raster_mask_at_points(
    points_utm: List[Tuple[float, float]],
    mask: np.ndarray,
    inv_transform: Any
) -> np.ndarray:
    """Checks whether given (x, y) coordinates fall on True in 2D mask."""
    h, w = mask.shape
    results = np.zeros(len(points_utm), dtype=bool)
    for i, (x, y) in enumerate(points_utm):
        c, r = inv_transform * (x, y)
        r_idx = int(np.clip(round(r), 0, h - 1))
        c_idx = int(np.clip(round(c), 0, w - 1))
        results[i] = mask[r_idx, c_idx]
    return results


def grade_buildings(
    buildings_gdf: gpd.GeoDataFrame,
    hazard_gdf: gpd.GeoDataFrame,
    cloud_nodata_mask: Optional[np.ndarray] = None,
    inv_transform: Any = None,
    utm_crs: str = "EPSG:32645",
    building_overlap_pct: float = 50.0,
    distance_damaged_m: float = 10.0,
    distance_possibly_damaged_m: float = 30.0
) -> gpd.GeoDataFrame:
    """
    Grades building damage using EMS-style taxonomy:
    - Destroyed: footprint overlaps Class 2 > X%
    - Damaged: overlaps Class 2 <= X%, or centroid within D1 m of Class 2
    - Possibly damaged: overlaps Class 3, or within D2 m of Class 2 (D2 > D1)
    - Not affected: otherwise
    - Cloud/no data around building: marked 'Unknown (cloud)', never 'Not affected'
    Each feature gets field 'evidence': 'observed' | 'inferred' | 'cloud-unknown'.
    """
    if len(buildings_gdf) == 0:
        return buildings_gdf.copy()

    b_utm = buildings_gdf.to_crs(utm_crs).copy()
    haz_utm = hazard_gdf.to_crs(utm_crs)

    c2_polys = haz_utm[haz_utm["class"] == 2]
    c3_polys = haz_utm[haz_utm["class"] == 3]

    c2_union = c2_polys.union_all() if len(c2_polys) > 0 else None
    c3_union = c3_polys.union_all() if len(c3_polys) > 0 else None

    centroids = b_utm.geometry.centroid
    areas = b_utm.geometry.area

    # Class 2 metrics
    if c2_union is not None and not c2_union.is_empty:
        c2_overlap_areas = b_utm.geometry.intersection(c2_union).area
        c2_overlap_pcts = (c2_overlap_areas / np.maximum(areas, 1e-3)) * 100.0
        c2_dists = centroids.distance(c2_union)
    else:
        c2_overlap_pcts = pd.Series(0.0, index=b_utm.index)
        c2_dists = pd.Series(99999.0, index=b_utm.index)

    # Class 3 metrics
    if c3_union is not None and not c3_union.is_empty:
        c3_intersects = b_utm.geometry.intersects(c3_union)
    else:
        c3_intersects = pd.Series(False, index=b_utm.index)

    # Cloud mask lookup
    if cloud_nodata_mask is not None and inv_transform is not None:
        coords = [(pt.x, pt.y) for pt in centroids]
        is_cloud = check_raster_mask_at_points(coords, cloud_nodata_mask, inv_transform)
    else:
        is_cloud = np.zeros(len(b_utm), dtype=bool)

    grades = []
    evidence = []

    for i in range(len(b_utm)):
        pct = float(c2_overlap_pcts.iloc[i])
        d = float(c2_dists.iloc[i])
        int_c3 = bool(c3_intersects.iloc[i])
        cloud = bool(is_cloud[i])

        if pct > building_overlap_pct:
            grades.append("Destroyed")
            evidence.append("observed")
        elif pct > 0.0 or d <= distance_damaged_m:
            grades.append("Damaged")
            evidence.append("observed")
        elif int_c3 or d <= distance_possibly_damaged_m:
            grades.append("Possibly damaged")
            evidence.append("inferred" if int_c3 else "observed")
        elif cloud:
            grades.append("Unknown (cloud)")
            evidence.append("cloud-unknown")
        else:
            grades.append("Not affected")
            evidence.append("observed")

    b_utm["damage_grade"] = grades
    b_utm["evidence"] = evidence
    b_utm["overlap_c2_pct"] = np.round(c2_overlap_pcts.values, 1)
    b_utm["dist_to_c2_m"] = np.round(c2_dists.values, 1)
    b_utm["area_m2"] = np.round(areas.values, 1)

    return b_utm.to_crs("EPSG:4326")


def grade_roads(
    roads_gdf: gpd.GeoDataFrame,
    hazard_gdf: gpd.GeoDataFrame,
    cloud_nodata_mask: Optional[np.ndarray] = None,
    inv_transform: Any = None,
    utm_crs: str = "EPSG:32645",
    segment_length_m: float = 100.0,
    distance_damaged_m: float = 10.0
) -> gpd.GeoDataFrame:
    """
    Segments road networks into segments <= segment_length_m and grades damage:
    - Intersects Class 2 = Destroyed (evidence: observed)
    - Intersects Class 3 or within D1 m of Class 2 = Possibly damaged (evidence: inferred/observed)
    - Otherwise: Not affected (or Unknown (cloud) if cloud-covered).
    """
    if len(roads_gdf) == 0:
        return roads_gdf.copy()

    r_utm = roads_gdf.to_crs(utm_crs).copy()
    haz_utm = hazard_gdf.to_crs(utm_crs)

    c2_polys = haz_utm[haz_utm["class"] == 2]
    c3_polys = haz_utm[haz_utm["class"] == 3]

    c2_union = c2_polys.union_all() if len(c2_polys) > 0 else None
    c3_union = c3_polys.union_all() if len(c3_polys) > 0 else None

    seg_records = []

    for idx, row in r_utm.iterrows():
        geom = row.geometry
        # If geometry is a bounding box polygon, extract centerline diagonal LineString
        if geom.geom_type == "Polygon":
            minx, miny, maxx, maxy = geom.bounds
            base_line = LineString([(minx, miny), (maxx, maxy)])
        elif geom.geom_type == "LineString":
            base_line = geom
        else:
            base_line = LineString(geom.boundary.coords) if hasattr(geom, "boundary") else None

        if base_line is None or base_line.length == 0:
            continue

        length = base_line.length
        if length <= segment_length_m:
            sub_lines = [base_line]
        else:
            n_chunks = max(1, int(np.ceil(length / segment_length_m)))
            chunk_len = length / n_chunks
            sub_lines = [
                substring(base_line, i * chunk_len, min((i + 1) * chunk_len, length))
                for i in range(n_chunks)
            ]

        for s_idx, s in enumerate(sub_lines):
            if s.length == 0:
                continue

            mid = s.interpolate(0.5, normalized=True)
            if cloud_nodata_mask is not None and inv_transform is not None:
                cloud = bool(check_raster_mask_at_points([(mid.x, mid.y)], cloud_nodata_mask, inv_transform)[0])
            else:
                cloud = False

            int_c2 = c2_union is not None and s.intersects(c2_union)
            int_c3 = c3_union is not None and s.intersects(c3_union)
            dist_c2 = c2_union is not None and (s.distance(c2_union) <= distance_damaged_m)

            if int_c2:
                grade = "Destroyed"
                ev = "observed"
            elif int_c3 or dist_c2:
                grade = "Possibly damaged"
                ev = "inferred" if int_c3 else "observed"
            elif cloud:
                grade = "Unknown (cloud)"
                ev = "cloud-unknown"
            else:
                grade = "Not affected"
                ev = "observed"

            rec = row.to_dict()
            rec["segment_id"] = f"{row.get('@osmId', 'way')}_{s_idx}"
            rec["damage_grade"] = grade
            rec["evidence"] = ev
            rec["length_m"] = round(float(s.length), 1)
            rec["length_km"] = round(float(s.length / 1000.0), 4)
            rec["geometry"] = s
            seg_records.append(rec)

    seg_gdf = gpd.GeoDataFrame(seg_records, crs=utm_crs)
    return seg_gdf.to_crs("EPSG:4326")


def grade_bridges(
    bridges_gdf: gpd.GeoDataFrame,
    hazard_gdf: gpd.GeoDataFrame,
    cloud_nodata_mask: Optional[np.ndarray] = None,
    inv_transform: Any = None,
    utm_crs: str = "EPSG:32645",
    distance_damaged_m: float = 10.0
) -> gpd.GeoDataFrame:
    """
    Grades bridge damage:
    - Intersects or within D1 m of Class 2 = Destroyed (evidence: observed)
    - Intersects Class 3 = Possibly damaged (evidence: inferred)
    - Otherwise = Not affected (or Unknown (cloud) if obscured).
    """
    if len(bridges_gdf) == 0:
        return bridges_gdf.copy()

    br_utm = bridges_gdf.to_crs(utm_crs).copy()
    haz_utm = hazard_gdf.to_crs(utm_crs)

    c2_polys = haz_utm[haz_utm["class"] == 2]
    c3_polys = haz_utm[haz_utm["class"] == 3]

    c2_union = c2_polys.union_all() if len(c2_polys) > 0 else None
    c3_union = c3_polys.union_all() if len(c3_polys) > 0 else None

    centroids = br_utm.geometry.centroid
    if cloud_nodata_mask is not None and inv_transform is not None:
        coords = [(pt.x, pt.y) for pt in centroids]
        is_cloud = check_raster_mask_at_points(coords, cloud_nodata_mask, inv_transform)
    else:
        is_cloud = np.zeros(len(br_utm), dtype=bool)

    grades = []
    evidence = []

    for i in range(len(br_utm)):
        geom = br_utm.geometry.iloc[i]
        cloud = bool(is_cloud[i])

        int_c2 = c2_union is not None and geom.intersects(c2_union)
        dist_c2 = c2_union is not None and (geom.distance(c2_union) <= distance_damaged_m)
        int_c3 = c3_union is not None and geom.intersects(c3_union)

        if int_c2 or dist_c2:
            grades.append("Destroyed")
            evidence.append("observed")
        elif int_c3:
            grades.append("Possibly damaged")
            evidence.append("inferred")
        elif cloud:
            grades.append("Unknown (cloud)")
            evidence.append("cloud-unknown")
        else:
            grades.append("Not affected")
            evidence.append("observed")

    br_utm["damage_grade"] = grades
    br_utm["evidence"] = evidence

    return br_utm.to_crs("EPSG:4326")
