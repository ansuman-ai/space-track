"""D8 Flow Direction and Downstream Drainage Path Tracer (Bonus).

Traces hydraulic drainage path downstream from any starting coordinate (lon, lat)
to the AOI edge using D8 steepest descent on Copernicus DEM-30 with priority-flood pit filling,
and finds settlements within a buffer distance (default 500 m) along with downstream distances.
"""

from __future__ import annotations

import heapq
import json
import logging
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import rasterio

logger = logging.getLogger("copilot.flowpath")


def haversine_m(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """Great-circle distance in meters between two coordinates."""
    r = 6371000.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2.0) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2.0) ** 2
    return 2.0 * r * math.asin(math.sqrt(a))


_FLOW_CACHE: Dict[str, Tuple[np.ndarray, np.ndarray, Any, np.ndarray]] = {}


def get_flow_directions(dem_path: Path | str) -> Tuple[np.ndarray, np.ndarray, Any, np.ndarray]:
    """Computes and caches cycle-free D8 flow directions using Barnes/Wang-Liu priority flood."""
    dem_p = Path(dem_path).resolve()
    key = str(dem_p)
    if key in _FLOW_CACHE:
        return _FLOW_CACHE[key]

    if not dem_p.exists():
        raise FileNotFoundError(f"DEM raster not found at: {dem_p}")

    with rasterio.open(dem_p) as src:
        dem = src.read(1).astype(np.float32)
        transform = src.transform
        h, w = dem.shape

    visited = np.zeros((h, w), dtype=bool)
    flow_r = np.full((h, w), -1, dtype=np.int32)
    flow_c = np.full((h, w), -1, dtype=np.int32)
    pq: List[Tuple[float, int, int]] = []

    # Enqueue boundary cells (outlets to AOI edge)
    for r in range(h):
        for c in (0, w - 1):
            if not visited[r, c]:
                heapq.heappush(pq, (float(dem[r, c]), r, c))
                visited[r, c] = True
    for c in range(w):
        for r in (0, h - 1):
            if not visited[r, c]:
                heapq.heappush(pq, (float(dem[r, c]), r, c))
                visited[r, c] = True

    dr = [-1, -1, -1,  0, 0,  1, 1, 1]
    dc = [-1,  0,  1, -1, 1, -1, 0, 1]

    while pq:
        elev, r, c = heapq.heappop(pq)
        for k in range(8):
            nr, nc = r + dr[k], c + dc[k]
            if 0 <= nr < h and 0 <= nc < w and not visited[nr, nc]:
                visited[nr, nc] = True
                flow_r[nr, nc] = r
                flow_c[nr, nc] = c
                val = float(dem[nr, nc])
                heapq.heappush(pq, (max(val, elev), nr, nc))

    _FLOW_CACHE[key] = (flow_r, flow_c, transform, dem)
    return _FLOW_CACHE[key]


def compute_d8_flow_path(
    dem_path: Path | str,
    start_lon: float,
    start_lat: float,
    max_steps: int = 5000,
) -> List[Dict[str, Any]]:
    """Compute D8 downstream path coordinates [lon, lat, elev, dist_from_start_km] from start to AOI edge."""
    flow_r, flow_c, transform, dem = get_flow_directions(dem_path)
    h, w = dem.shape

    # Locate start cell
    c_start, r_start = ~transform * (start_lon, start_lat)
    curr_r, curr_c = int(round(r_start)), int(round(c_start))

    if not (0 <= curr_r < h and 0 <= curr_c < w):
        curr_r = max(0, min(h - 1, curr_r))
        curr_c = max(0, min(w - 1, curr_c))

    path_nodes: List[Dict[str, Any]] = []
    visited_cells = set()
    total_dist_m = 0.0
    prev_lon, prev_lat = None, None

    while 0 <= curr_r < h and 0 <= curr_c < w and len(path_nodes) < max_steps:
        if (curr_r, curr_c) in visited_cells:
            break
        visited_cells.add((curr_r, curr_c))

        lon, lat = transform * (curr_c + 0.5, curr_r + 0.5)
        elev = float(dem[curr_r, curr_c])

        if prev_lon is not None:
            total_dist_m += haversine_m(prev_lon, prev_lat, lon, lat)
        prev_lon, prev_lat = lon, lat

        path_nodes.append({
            "lon": round(float(lon), 6),
            "lat": round(float(lat), 6),
            "elevation_m": round(float(elev), 1),
            "distance_downstream_km": round(total_dist_m / 1000.0, 3),
        })

        nr, nc = flow_r[curr_r, curr_c], flow_c[curr_r, curr_c]
        if nr < 0 or nc < 0:
            break
        curr_r, curr_c = nr, nc

    return path_nodes


def find_downstream_settlements(
    path_nodes: List[Dict[str, Any]],
    settlements_geojson_path: Path | str,
    buffer_distance_m: float = 500.0,
) -> List[Dict[str, Any]]:
    """Identify settlements within buffer_distance_m of the downstream flow path, ranked by distance."""
    s_path = Path(settlements_geojson_path).resolve()
    if not s_path.exists():
        return []

    with open(s_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not path_nodes:
        return []

    # Fast metric distance query
    found_settlements = []
    for feat in data.get("features", []):
        geom = feat.get("geometry", {})
        props = feat.get("properties", {})
        if geom.get("type") != "Point":
            continue
        s_lon, s_lat = geom["coordinates"][0], geom["coordinates"][1]

        # Find min distance to any path node
        min_offset_m = float("inf")
        downstream_km = 0.0

        for node in path_nodes:
            d = haversine_m(s_lon, s_lat, node["lon"], node["lat"])
            if d < min_offset_m:
                min_offset_m = d
                downstream_km = node["distance_downstream_km"]

        if min_offset_m <= buffer_distance_m:
            name = props.get("name") or f"Settlement at ({s_lat:.4f}, {s_lon:.4f})"
            bldgs = props.get("building_count", 0)
            status = props.get("vehicle_status_opt", "unknown")
            found_settlements.append({
                "settlement_id": props.get("settlement_id", ""),
                "name": name,
                "building_count": bldgs,
                "access_status": status,
                "distance_downstream_km": round(downstream_km, 2),
                "lateral_offset_m": round(min_offset_m, 1),
                "lon": round(s_lon, 5),
                "lat": round(s_lat, 5),
            })

    # Sort primarily by downstream distance along the river flow
    found_settlements.sort(key=lambda x: x["distance_downstream_km"])
    return found_settlements
