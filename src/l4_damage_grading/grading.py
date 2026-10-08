"""
Critical Infrastructure Damage Grading Engine.
Applies EMS-style damage classification to buildings, roads, and bridges
conditioned on Layer 2 flood hazard polygons (Class 2: Observed, Class 3: Inferred)
and cloud/nodata validity masks.
"""

from typing import Dict, Any, Tuple, List, Optional
import numpy as np
import pandas as pd
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
    utm_crs: Optional[str] = None,
    building_overlap_pct: float = 50.0,
    distance_damaged_m: float = 10.0,
    distance_possibly_damaged_m: float = 30.0,
    is_flat_floodplain: bool = False
) -> gpd.GeoDataFrame:
    """
    Grades building damage using EMS-style taxonomy:
    - Destroyed: footprint overlaps Class 2 > X%
    - Damaged: overlaps Class 2 <= X%, or centroid within D1 m of Class 2
    - Possibly damaged: overlaps Class 3, or within D2 m of Class 2 (D2 > D1)
    - Not affected: otherwise
    - Cloud/no data around building: marked 'Unknown (cloud)' for steep valleys, or graded from S1 on flat floodplains.
    Each feature gets field 'evidence': 'observed' | 'inferred' | 'cloud-unknown' | 'observed-s1'.
    """
    if len(buildings_gdf) == 0:
        return buildings_gdf.copy()

    if utm_crs is None or utm_crs == "auto":
        from src.common.crs_utils import auto_utm_crs
        if len(buildings_gdf) > 0 and buildings_gdf.crs:
            b_wgs = buildings_gdf.to_crs("EPSG:4326")
            utm_crs = auto_utm_crs(b_wgs.total_bounds)
        elif len(hazard_gdf) > 0 and hazard_gdf.crs:
            h_wgs = hazard_gdf.to_crs("EPSG:4326")
            utm_crs = auto_utm_crs(h_wgs.total_bounds)
        else:
            raise ValueError("utm_crs must be provided when geodataframes are empty.")

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
    if cloud_nodata_mask is not None and inv_transform is not None and not is_flat_floodplain:
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

        if is_flat_floodplain:
            if pct > 0.0 or d <= distance_damaged_m:
                grades.append("Flooded")
                evidence.append("observed-s1")
            elif int_c3 or d <= distance_possibly_damaged_m:
                grades.append("Possibly flooded")
                evidence.append("observed-s1")
            else:
                grades.append("Not affected")
                evidence.append("observed-s1")
        else:
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
    utm_crs: Optional[str] = None,
    segment_length_m: float = 100.0,
    distance_damaged_m: float = 10.0,
    is_flat_floodplain: bool = False
) -> gpd.GeoDataFrame:
    """
    Segments road networks into segments <= segment_length_m and grades damage:
    - Intersects Class 2 = Destroyed (evidence: observed)
    - Intersects Class 3 or within D1 m of Class 2 = Possibly damaged (evidence: inferred/observed)
    - Otherwise: Not affected (or Unknown (cloud) if cloud-covered in steep valleys; graded from S1 in flat floodplains).
    """
    if len(roads_gdf) == 0:
        return roads_gdf.copy()

    if utm_crs is None or utm_crs == "auto":
        from src.common.crs_utils import auto_utm_crs
        if len(roads_gdf) > 0 and roads_gdf.crs:
            r_wgs = roads_gdf.to_crs("EPSG:4326")
            utm_crs = auto_utm_crs(r_wgs.total_bounds)
        elif len(hazard_gdf) > 0 and hazard_gdf.crs:
            h_wgs = hazard_gdf.to_crs("EPSG:4326")
            utm_crs = auto_utm_crs(h_wgs.total_bounds)
        else:
            raise ValueError("utm_crs must be provided when geodataframes are empty.")

    r_utm = roads_gdf.to_crs(utm_crs).copy()
    haz_utm = hazard_gdf.to_crs(utm_crs)

    c2_polys = haz_utm[haz_utm["class"] == 2]
    c3_polys = haz_utm[haz_utm["class"] == 3]

    c2_union = c2_polys.union_all() if len(c2_polys) > 0 else None
    c3_union = c3_polys.union_all() if len(c3_polys) > 0 else None

    seg_records = []

    for idx, row in r_utm.iterrows():
        geom = row.geometry
        if geom is None or geom.is_empty:
            continue

        if geom.geom_type == "Polygon":
            minx, miny, maxx, maxy = geom.bounds
            base_lines = [LineString([(minx, miny), (maxx, maxy)])]
        elif geom.geom_type == "LineString":
            base_lines = [geom]
        elif geom.geom_type == "MultiLineString":
            base_lines = [ls for ls in geom.geoms if ls.length > 0]
        else:
            continue

        for base_line in base_lines:
            if base_line.length == 0:
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
            if cloud_nodata_mask is not None and inv_transform is not None and not is_flat_floodplain:
                cloud = bool(check_raster_mask_at_points([(mid.x, mid.y)], cloud_nodata_mask, inv_transform)[0])
            else:
                cloud = False

            int_c2 = c2_union is not None and s.intersects(c2_union)
            int_c3 = c3_union is not None and s.intersects(c3_union)
            dist_c2 = c2_union is not None and (s.distance(c2_union) <= distance_damaged_m)

            if int_c2:
                grade = "Destroyed"
                ev = "observed-s1" if is_flat_floodplain else "observed"
            elif int_c3 or dist_c2:
                grade = "Possibly damaged"
                ev = "observed-s1" if is_flat_floodplain else ("inferred" if int_c3 else "observed")
            elif cloud:
                grade = "Unknown (cloud)"
                ev = "cloud-unknown"
            else:
                grade = "Not affected"
                ev = "observed-s1" if is_flat_floodplain else "observed"

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
    waterways_gdf: Optional[gpd.GeoDataFrame] = None,
    hazard_raster: Optional[np.ndarray] = None,
    transform_matrix: Any = None,
    cloud_nodata_mask: Optional[np.ndarray] = None,
    inv_transform: Any = None,
    utm_crs: Optional[str] = None,
    bridge_distance_m: float = 30.0,
    bridge_reach_radius_m: float = 100.0,
    distance_damaged_m: Optional[float] = None,
    is_flat_floodplain: bool = False
) -> gpd.GeoDataFrame:
    """
    Grades bridge damage using principled spatial proximity and river reach rules:
    1. Distance rule: within bridge_distance_m (D_bridge, default 30 m) of Class 2 = Destroyed;
       within bridge_distance_m of Class 3 = Possibly damaged.
    2. Reach rule: if bridge crosses an OSM waterway=river reach and Class 2 or 3 is found along
       that reach within bridge_reach_radius_m (R, default 100 m) upstream/downstream:
       - Class 2 along reach = Destroyed (evidence: observed, rule: reach)
       - Class 3 along reach = Possibly damaged (evidence: inferred, rule: reach)
    3. Adds fields:
       - 'damage_grade': 'Destroyed' | 'Possibly damaged' | 'Not affected' | 'Unknown (cloud)'
       - 'evidence': 'observed' | 'inferred' | 'cloud-unknown'
       - 'rule': 'reach' | 'distance' | 'none'
       - 'distance_m': distance to triggering hazard or along reach
    """
    if len(bridges_gdf) == 0:
        return bridges_gdf.copy()

    if utm_crs is None or utm_crs == "auto":
        from src.common.crs_utils import auto_utm_crs
        if len(bridges_gdf) > 0 and bridges_gdf.crs:
            br_wgs = bridges_gdf.to_crs("EPSG:4326")
            utm_crs = auto_utm_crs(br_wgs.total_bounds)
        elif len(hazard_gdf) > 0 and hazard_gdf.crs:
            h_wgs = hazard_gdf.to_crs("EPSG:4326")
            utm_crs = auto_utm_crs(h_wgs.total_bounds)
        else:
            raise ValueError("utm_crs must be provided when geodataframes are empty.")

    if distance_damaged_m is not None:
        # backward compatibility if explicitly provided
        pass

    br_utm = bridges_gdf.to_crs(utm_crs).copy()
    haz_utm = hazard_gdf.to_crs(utm_crs)

    c2_polys = haz_utm[haz_utm["class"] == 2]
    c3_polys = haz_utm[haz_utm["class"] == 3]

    c2_union = c2_polys.union_all() if len(c2_polys) > 0 else None
    c3_union = c3_polys.union_all() if len(c3_polys) > 0 else None

    # Waterways river reaches
    if waterways_gdf is not None and len(waterways_gdf) > 0:
        w_utm = waterways_gdf.to_crs(utm_crs)
        rivers = w_utm[w_utm["waterway"] == "river"]
    else:
        rivers = gpd.GeoDataFrame(columns=["geometry"], crs=utm_crs)

    # Precompute raster distance maps if raster available
    d2_map = None
    d3_map = None
    if hazard_raster is not None and transform_matrix is not None:
        from scipy.ndimage import distance_transform_edt
        px_size = abs(transform_matrix.a) if hasattr(transform_matrix, "a") else 10.0
        if np.any(hazard_raster == 2):
            d2_map = distance_transform_edt(hazard_raster != 2) * px_size
        if np.any(hazard_raster == 3):
            d3_map = distance_transform_edt(hazard_raster != 3) * px_size

    centroids = br_utm.geometry.centroid
    if cloud_nodata_mask is not None and inv_transform is not None:
        coords = [(pt.x, pt.y) for pt in centroids]
        is_cloud = check_raster_mask_at_points(coords, cloud_nodata_mask, inv_transform)
    else:
        is_cloud = np.zeros(len(br_utm), dtype=bool)

    from rasterio.features import rasterize

    grades = []
    evidence = []
    rules = []
    applied_dists = []
    dists_c2_all = []
    dists_c3_all = []

    for i in range(len(br_utm)):
        geom = br_utm.geometry.iloc[i]
        cloud = bool(is_cloud[i])

        # 1. Distance to Class 2
        d_c2_poly = float(geom.distance(c2_union)) if c2_union is not None else 99999.0
        if d2_map is not None:
            m = rasterize([geom], out_shape=hazard_raster.shape, transform=transform_matrix, fill=0, default_value=1, dtype=np.uint8) == 1
            if np.any(m):
                d_c2_ras = float(np.min(d2_map[m]))
            else:
                col, row_idx = ~transform_matrix * (geom.centroid.x, geom.centroid.y)
                r_i = int(np.clip(round(row_idx), 0, hazard_raster.shape[0] - 1))
                c_i = int(np.clip(round(col), 0, hazard_raster.shape[1] - 1))
                d_c2_ras = float(d2_map[r_i, c_i])
            d_c2 = min(d_c2_poly, d_c2_ras)
        else:
            d_c2 = d_c2_poly

        # 2. Distance to Class 3
        d_c3_poly = float(geom.distance(c3_union)) if c3_union is not None else 99999.0
        if d3_map is not None:
            m = rasterize([geom], out_shape=hazard_raster.shape, transform=transform_matrix, fill=0, default_value=1, dtype=np.uint8) == 1
            if np.any(m):
                d_c3_ras = float(np.min(d3_map[m]))
            else:
                col, row_idx = ~transform_matrix * (geom.centroid.x, geom.centroid.y)
                r_i = int(np.clip(round(row_idx), 0, hazard_raster.shape[0] - 1))
                c_i = int(np.clip(round(col), 0, hazard_raster.shape[1] - 1))
                d_c3_ras = float(d3_map[r_i, c_i])
            d_c3 = min(d_c3_poly, d_c3_ras)
        else:
            d_c3 = d_c3_poly

        dists_c2_all.append(d_c2)
        dists_c3_all.append(d_c3)

        # 3. Check river reach crossings
        reach_c2 = False
        reach_c3 = False
        reach_dist_c2 = 99999.0
        reach_dist_c3 = 99999.0

        for _, r_row in rivers.iterrows():
            r_line = r_row.geometry
            if geom.intersects(r_line):
                inter = geom.intersection(r_line)
                reach_buf = r_line.intersection(inter.buffer(bridge_reach_radius_m))
                if c2_union is not None and reach_buf.intersects(c2_union):
                    reach_c2 = True
                    pt = inter if inter.geom_type == "Point" else inter.centroid
                    pos = r_line.project(pt)
                    for step in range(0, int(bridge_reach_radius_m) + 1, 1):
                        p_fwd = min(r_line.length, pos + step)
                        p_bwd = max(0.0, pos - step)
                        if r_line.interpolate(p_fwd).intersects(c2_union) or r_line.interpolate(p_bwd).intersects(c2_union):
                            reach_dist_c2 = min(reach_dist_c2, float(step))
                            break
                if c3_union is not None and reach_buf.intersects(c3_union):
                    reach_c3 = True
                    pt = inter if inter.geom_type == "Point" else inter.centroid
                    pos = r_line.project(pt)
                    for step in range(0, int(bridge_reach_radius_m) + 1, 1):
                        p_fwd = min(r_line.length, pos + step)
                        p_bwd = max(0.0, pos - step)
                        if r_line.interpolate(p_fwd).intersects(c3_union) or r_line.interpolate(p_bwd).intersects(c3_union):
                            reach_dist_c3 = min(reach_dist_c3, float(step))
                            break

        # 4. Grading classification & rule assignment
        if reach_c2:
            grades.append("Flooded / impassable" if is_flat_floodplain else "Destroyed")
            rules.append("reach")
            evidence.append("observed-s1" if is_flat_floodplain else "observed")
            applied_dists.append(round(reach_dist_c2 if reach_dist_c2 < 99999.0 else d_c2, 1))
        elif d_c2 <= bridge_distance_m:
            grades.append("Flooded / impassable" if is_flat_floodplain else "Destroyed")
            rules.append("distance")
            evidence.append("observed-s1" if is_flat_floodplain else "observed")
            applied_dists.append(round(d_c2, 1))
        elif reach_c3:
            grades.append("Possibly flooded" if is_flat_floodplain else "Possibly damaged")
            rules.append("reach")
            evidence.append("observed-s1" if is_flat_floodplain else "inferred")
            applied_dists.append(round(reach_dist_c3 if reach_dist_c3 < 99999.0 else d_c3, 1))
        elif d_c3 <= bridge_distance_m:
            grades.append("Possibly flooded" if is_flat_floodplain else "Possibly damaged")
            rules.append("distance")
            evidence.append("observed-s1" if is_flat_floodplain else "inferred")
            applied_dists.append(round(d_c3, 1))
        elif cloud and not is_flat_floodplain:
            grades.append("Unknown (cloud)")
            rules.append("none")
            evidence.append("cloud-unknown")
            applied_dists.append(round(min(d_c2, d_c3), 1))
        else:
            grades.append("Not affected")
            rules.append("none")
            evidence.append("observed-s1" if is_flat_floodplain else "observed")
            applied_dists.append(round(min(d_c2, d_c3), 1))

    br_utm["damage_grade"] = grades
    br_utm["evidence"] = evidence
    br_utm["rule"] = rules
    br_utm["distance_m"] = applied_dists
    br_utm["dist_to_c2_m"] = [round(x, 1) for x in dists_c2_all]
    br_utm["dist_to_c3_m"] = [round(x, 1) for x in dists_c3_all]

    return br_utm.to_crs("EPSG:4326")

