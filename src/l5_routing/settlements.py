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


def extract_settlements(
    places_path: str = "data/raw/osm_buffered/osm_places.geojson",
    buildings_path: str = "data/raw/osm/osm_buildings.geojson",
    bbox: List[float] = [85.30, 28.10, 85.42, 28.25],
    eps_m: float = 65.0,
    min_samples: int = 5,
    utm_crs: str = "EPSG:32645"
) -> gpd.GeoDataFrame:
    """
    Extracts settlements in the study area:
    - Named place nodes inside bbox
    - Unnamed groups from DBSCAN clusters of buildings, named after nearest place node
    """
    bbox_deg = box(*bbox)
    places_all = gpd.read_file(places_path)
    p_in = places_all[places_all.geometry.intersects(bbox_deg)].to_crs(utm_crs).copy()

    b_gdf = gpd.read_file(buildings_path).to_crs(utm_crs)
    b_pts = np.array([(p.x, p.y) for p in b_gdf.geometry.centroid])

    # Cluster buildings
    labels = dbscan_clustering(b_pts, eps=eps_m, min_samples=min_samples)
    n_clusters = len(set(labels)) - (1 if -1 in labels else 0)

    p_pts = np.array([(p.geometry.x, p.geometry.y) for _, p in p_in.iterrows()])
    p_tree = cKDTree(p_pts)

    settlements_records = []
    matched_clusters = set()

    # 1. Place nodes in bbox
    for idx, p_row in p_in.iterrows():
        p_x, p_y = p_row.geometry.x, p_row.geometry.y
        name = p_row.get("name")
        oid = p_row.get("@osmId", f"node_{idx}")
        if name is None or str(name) == "nan":
            name = f"Place {oid}"

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
    for c_id in range(n_clusters):
        if c_id in matched_clusters:
            continue
        c_pts = b_pts[labels == c_id]
        cx, cy = np.mean(c_pts, axis=0)
        d, p_idx = p_tree.query([cx, cy])
        near_p = p_in.iloc[p_idx]
        near_name = near_p.get("name")
        if near_name is None or str(near_name) == "nan":
            near_name = f"Place {near_p.get('@osmId')}"

        c_name = f"Cluster near {near_name} (ID {c_id})"
        settlements_records.append({
            "settlement_id": f"cluster_{c_id}",
            "name": c_name,
            "type": "building_cluster",
            "building_count": int(len(c_pts)),
            "population": "not available",
            "geometry": Point(float(cx), float(cy))
        })

    settlements_gdf = gpd.GeoDataFrame(settlements_records, crs=utm_crs)
    return settlements_gdf
