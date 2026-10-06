"""
Settlement Identification and Clustering for Layer 5.
Combines OSM place nodes in the study bbox with DBSCAN clusters of OSM buildings
for unnamed settlement groups.
"""

from typing import List, Dict, Any, Optional
import numpy as np
import geopandas as gpd
from shapely.geometry import Point, box
from scipy.spatial import cKDTree


def dbscan_clustering(
    points: np.ndarray,
    eps: float = 65.0,
    min_samples: int = 5
) -> np.ndarray:
    """Fast cKDTree-based DBSCAN clustering."""
    tree = cKDTree(points)
    n = len(points)
    labels = np.full(n, -1, dtype=int)
    cluster_id = 0
    visited = np.zeros(n, dtype=bool)
    neighbors = tree.query_ball_point(points, r=eps)

    for i in range(n):
        if visited[i]:
            continue
        visited[i] = True
        if len(neighbors[i]) < min_samples:
            continue

        labels[i] = cluster_id
        queue = list(neighbors[i])
        idx = 0
        while idx < len(queue):
            pt = queue[idx]
            idx += 1
            if not visited[pt]:
                visited[pt] = True
                if len(neighbors[pt]) >= min_samples:
                    queue.extend([x for x in neighbors[pt] if x not in queue])
            if labels[pt] == -1:
                labels[pt] = cluster_id
        cluster_id += 1

    return labels


def format_place_name(p_row: Any) -> str:
    """Format place name: use name:en if present, else name, keeping Nepali in brackets."""
    en = p_row.get("name:en")
    ne = p_row.get("name:ne")
    raw_name = p_row.get("name")

    en_str = str(en).strip() if en is not None and str(en) != "nan" and str(en).strip() != "" else None
    ne_str = str(ne).strip() if ne is not None and str(ne) != "nan" and str(ne).strip() != "" else None
    raw_str = str(raw_name).strip() if raw_name is not None and str(raw_name) != "nan" and str(raw_name).strip() != "" else None

    if en_str:
        if ne_str and ne_str != en_str:
            return f"{en_str} ({ne_str})"
        elif raw_str and raw_str != en_str:
            return f"{en_str} ({raw_str})"
        else:
            return en_str
    elif raw_str:
        if ne_str and ne_str != raw_str:
            return f"{raw_str} ({ne_str})"
        return raw_str
    elif ne_str:
        return ne_str
    else:
        oid = p_row.get("@osmId", "unknown")
        return f"Place {oid}"


def extract_settlements(
    places_path: str = "data/raw/osm_buffered/osm_places.geojson",
    buildings_path: str = "data/raw/osm/osm_buildings.geojson",
    bbox: List[float] = None,
    eps_m: float = 65.0,
    min_samples: int = 5,
    named_place_max_distance_m: float = 500.0,
    utm_crs: str = "EPSG:32645"
) -> gpd.GeoDataFrame:
    """
    Extracts settlements in the study area:
    - Named place nodes inside bbox
    - Unnamed groups from DBSCAN clusters of buildings:
      - Within named_place_max_distance_m: named after nearest place node
      - Beyond threshold: "Unnamed settlement at lat, lon (nearest named place: NAME, D km)"
    """
    bbox_deg = box(*bbox)
    places_all = gpd.read_file(places_path)
    p_in = places_all[places_all.geometry.intersects(bbox_deg)].to_crs(utm_crs).copy()
    if "@osmId" in p_in.columns:
        p_in = p_in.sort_values(by=["@osmId"]).reset_index(drop=True)
    elif "id" in p_in.columns:
        p_in = p_in.sort_values(by=["id"]).reset_index(drop=True)

    b_gdf = gpd.read_file(buildings_path).to_crs(utm_crs)
    if "@osmId" in b_gdf.columns:
        b_gdf = b_gdf.sort_values(by=["@osmId"]).reset_index(drop=True)
    elif "id" in b_gdf.columns:
        b_gdf = b_gdf.sort_values(by=["id"]).reset_index(drop=True)
    b_pts = np.array([(p.x, p.y) for p in b_gdf.geometry.centroid])

    # Cluster buildings
    labels = dbscan_clustering(b_pts, eps=eps_m, min_samples=min_samples)
    n_clusters = len(set(labels)) - (1 if -1 in labels else 0)

    # Named place nodes for distance calculations
    p_named = p_in[p_in["name"].notna() & (p_in["name"].astype(str) != "") & (p_in["name"].astype(str) != "nan")].copy()
    if len(p_named) > 0:
        p_named_pts = np.array([(p.geometry.x, p.geometry.y) for _, p in p_named.iterrows()])
        p_named_tree = cKDTree(p_named_pts)
    else:
        p_named_tree = None

    settlements_records = []
    matched_clusters = set()

    # 1. Place nodes in bbox
    for idx, p_row in p_in.iterrows():
        p_x, p_y = p_row.geometry.x, p_row.geometry.y
        name = format_place_name(p_row)
        oid = p_row.get("@osmId", f"node_{idx}")

        pop = p_row.get("population")
        pop_str = str(pop) if pop is not None and str(pop) != "nan" and str(pop).strip() != "" else "not available"

        # Associate building count
        dists = np.hypot(b_pts[:, 0] - p_x, b_pts[:, 1] - p_y)
        close_mask = dists <= 150.0
        c_ids = labels[close_mask]
        c_ids_valid = c_ids[c_ids >= 0]
        if len(c_ids_valid) > 0:
            main_c = int(np.bincount(c_ids_valid).argmax())
            matched_clusters.add(main_c)
            b_count = int(np.sum(labels == main_c))
        else:
            b_count = int(np.sum(close_mask))

        settlements_records.append({
            "settlement_id": str(oid),
            "name": str(name),
            "type": "place_node",
            "building_count": b_count,
            "population": pop_str,
            "geometry": Point(p_x, p_y)
        })

    # 2. Unnamed DBSCAN clusters
    cluster_candidates = []
    for c_id in range(n_clusters):
        if c_id in matched_clusters:
            continue
        c_pts = b_pts[labels == c_id]
        cx, cy = np.mean(c_pts, axis=0)
        cluster_candidates.append({
            "c_pts": c_pts,
            "cx": float(cx),
            "cy": float(cy),
        })

    # Canonical sorting: largest clusters first, break ties with coordinates
    cluster_candidates.sort(key=lambda c: (-len(c["c_pts"]), round(c["cx"], 2), round(c["cy"], 2)))

    for c_idx, c_info in enumerate(cluster_candidates):
        c_pts = c_info["c_pts"]
        cx, cy = c_info["cx"], c_info["cy"]

        # Coordinate in WGS84 (lat, lon)
        pt_wgs = gpd.GeoSeries([Point(cx, cy)], crs=utm_crs).to_crs("EPSG:4326").iloc[0]
        lat, lon = pt_wgs.y, pt_wgs.x

        if p_named_tree is not None:
            d_m, p_idx = p_named_tree.query([cx, cy])
            near_p = p_named.iloc[p_idx]
            near_name = format_place_name(near_p)
            d_km = d_m / 1000.0
        else:
            d_m = float("inf")
            near_name = "Unknown"
            d_km = 0.0

        if d_m <= named_place_max_distance_m:
            c_name = f"Cluster near {near_name} (ID {c_idx})"
        else:
            c_name = f"Unnamed settlement at {lat:.4f}, {lon:.4f} (nearest named place: {near_name}, {d_km:.1f} km)"

        settlements_records.append({
            "settlement_id": f"cluster_{c_idx}",
            "name": c_name,
            "type": "building_cluster",
            "building_count": int(len(c_pts)),
            "population": "not available",
            "geometry": Point(float(cx), float(cy))
        })

    settlements_gdf = gpd.GeoDataFrame(settlements_records, crs=utm_crs)
    return settlements_gdf
