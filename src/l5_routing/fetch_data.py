"""
Buffered OpenStreetMap Data Ingestion for Layer 5 Routing.
Fetches pre-event OSM geometries using ohsome geometry extraction
over a buffered bounding box around the event study area.
"""

import os
import sys
import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple
import numpy as np
import geopandas as gpd
from pyproj import Transformer

from src.l0_ingestion.fetch_osm import query_ohsome_layer, get_latest_ohsome_timestamp

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("l5_fetch_osm")

OSM_BUFFER_QUERIES = {
    "roads": "highway=* and geometry:line",
    "bridges": "bridge=* and bridge!=no and geometry:line",
    "hospitals": "(amenity=hospital or amenity=clinic or amenity=doctors or healthcare=hospital) and (geometry:point or geometry:polygon)",
    "places": "(place=city or place=town or place=village or place=hamlet or place=isolated_dwelling) and geometry:point"
}


def compute_buffered_bbox(
    bbox: List[float],
    buffer_km: float = 30.0,
    utm_crs: Optional[str] = None
) -> List[float]:
    """Expands WGS84 bbox [min_lon, min_lat, max_lon, max_lat] by buffer_km in UTM."""
    if utm_crs is None or utm_crs == "auto":
        from src.common.crs_utils import auto_utm_crs
        utm_crs = auto_utm_crs(bbox)
    to_utm = Transformer.from_crs("EPSG:4326", utm_crs, always_xy=True)
    to_wgs = Transformer.from_crs(utm_crs, "EPSG:4326", always_xy=True)

    x1, y1 = to_utm.transform(bbox[0], bbox[1])
    x2, y2 = to_utm.transform(bbox[2], bbox[3])

    buf_m = buffer_km * 1000.0
    x_min, y_min = min(x1, x2) - buf_m, min(y1, y2) - buf_m
    x_max, y_max = max(x1, x2) + buf_m, max(y1, y2) + buf_m

    lon_min, lat_min = to_wgs.transform(x_min, y_min)
    lon_max, lat_max = to_wgs.transform(x_max, y_max)

    return [round(float(lon_min), 4), round(float(lat_min), 4),
            round(float(lon_max), 4), round(float(lat_max), 4)]


def compute_layer_vertex_stats(gdf: gpd.GeoDataFrame) -> Dict[str, Any]:
    """Computes vertex statistics (min, median, max) and geometry type breakdown."""
    if len(gdf) == 0:
        return {"count": 0, "geom_types": {}, "min_vertices": 0, "median_vertices": 0.0, "max_vertices": 0}

    geom_types = gdf.geometry.geom_type.value_counts().to_dict()
    vertex_counts = []
    for g in gdf.geometry:
        if g is None or g.is_empty:
            continue
        if g.geom_type == "Point":
            vertex_counts.append(1)
        elif g.geom_type in ["LineString", "LinearRing"]:
            vertex_counts.append(len(g.coords))
        elif g.geom_type == "Polygon":
            vertex_counts.append(len(g.exterior.coords))
        elif g.geom_type == "MultiPolygon":
            vertex_counts.append(sum(len(p.exterior.coords) for p in g.geoms))
        elif g.geom_type == "MultiLineString":
            vertex_counts.append(sum(len(ls.coords) for ls in g.geoms))

    if not vertex_counts:
        return {"count": len(gdf), "geom_types": geom_types, "min_vertices": 0, "median_vertices": 0.0, "max_vertices": 0}

    vc = np.array(vertex_counts)
    return {
        "count": len(gdf),
        "geom_types": geom_types,
        "min_vertices": int(vc.min()),
        "median_vertices": float(np.median(vc)),
        "max_vertices": int(vc.max())
    }


def match_buf_roads(f: Dict[str, Any]) -> bool:
    props = f.get("properties", {})
    gtype = f.get("geometry", {}).get("type", "")
    is_geom = gtype in ("LineString", "MultiLineString")
    hw = props.get("highway")
    return is_geom and bool(hw)


def match_buf_bridges(f: Dict[str, Any]) -> bool:
    props = f.get("properties", {})
    gtype = f.get("geometry", {}).get("type", "")
    is_geom = gtype in ("LineString", "MultiLineString")
    br = props.get("bridge")
    return is_geom and bool(br) and br != "no"


def match_buf_hospitals(f: Dict[str, Any]) -> bool:
    props = f.get("properties", {})
    gtype = f.get("geometry", {}).get("type", "")
    is_geom = gtype in ("Point", "MultiPoint", "Polygon", "MultiPolygon")
    am = props.get("amenity")
    hc = props.get("healthcare")
    return is_geom and (am in ("hospital", "clinic", "doctors") or hc == "hospital")


def match_buf_places(f: Dict[str, Any]) -> bool:
    props = f.get("properties", {})
    gtype = f.get("geometry", {}).get("type", "")
    is_geom = gtype in ("Point", "MultiPoint")
    pl = props.get("place")
    return is_geom and pl in ("city", "town", "village", "hamlet", "isolated_dwelling")


BUFFER_LAYER_MATCHERS = {
    "roads": match_buf_roads,
    "bridges": match_buf_bridges,
    "hospitals": match_buf_hospitals,
    "places": match_buf_places,
}


def fetch_buffered_osm(
    bbox: List[float],
    buffer_km: float = 30.0,
    event_date: Optional[str] = None,
    out_dir: str = "data/raw/osm_buffered",
    utm_crs: Optional[str] = None,
    days_before: int = 1,
    force: bool = False
) -> Dict[str, Any]:
    """
    Fetches pre-event OSM layers over the 30 km buffered area:
    roads, paths/footways/tracks, bridges, hospitals, places.
    Uses a single combined ohsome query and splits features locally by tags.
    """
    if utm_crs is None or utm_crs == "auto":
        from src.common.crs_utils import auto_utm_crs
        utm_crs = auto_utm_crs(bbox)
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    summary_file = out_path / "osm_buffered_summary.json"

    buf_bbox = compute_buffered_bbox(bbox, buffer_km=buffer_km, utm_crs=utm_crs)
    logger.info(f"Target buffered bbox ({buffer_km} km buffer): {buf_bbox}")

    if not force and summary_file.exists() and all((out_path / f"osm_{k}.geojson").exists() for k in OSM_BUFFER_QUERIES):
        try:
            with open(summary_file, "r") as f:
                cached = json.load(f)
            logger.info(f"Verified existing buffered OSM layers in {out_dir}")
            return cached
        except Exception:
            pass

    latest_ts = get_latest_ohsome_timestamp()
    if event_date:
        ev_dt = datetime.fromisoformat(event_date)
        pre_event_dt = (ev_dt - timedelta(days=days_before)).strftime("%Y-%m-%dT00:00:00Z")
        snapshot_time = min(pre_event_dt, latest_ts)
    else:
        snapshot_time = latest_ts
    logger.info(f"Pre-event snapshot timestamp: {snapshot_time}")

    combined_filter = " or ".join(f"({v})" for v in OSM_BUFFER_QUERIES.values())
    logger.info("Executing single combined ohsome geometry extraction query for all buffered layers...")
    import time
    t_q0 = time.time()
    geojson_res = query_ohsome_layer(buf_bbox, combined_filter, snapshot_time)
    t_q1 = time.time()
    all_features = geojson_res.get("features", [])
    logger.info(f"Combined buffered OSM query returned {len(all_features)} total features in {t_q1 - t_q0:.2f}s")

    stats = {}
    for layer_name, matcher in BUFFER_LAYER_MATCHERS.items():
        layer_file = out_path / f"osm_{layer_name}.geojson"
        layer_feats = [f for f in all_features if matcher(f)]
        layer_feats.sort(key=lambda f: str(f.get("properties", {}).get("@osmId", "") or f.get("id", "")))
        layer_res = {
            "attribution": geojson_res.get("attribution", {}),
            "apiVersion": geojson_res.get("apiVersion", ""),
            "type": "FeatureCollection",
            "features": layer_feats
        }
        with open(layer_file, "w") as f:
            json.dump(layer_res, f)
        logger.info(f"Saved {len(layer_feats)} features to {layer_file}")
        gdf = gpd.read_file(layer_file)
        l_stats = compute_layer_vertex_stats(gdf)
        stats[layer_name] = l_stats
        print(f"=== Layer: {layer_name} ===")
        print(f"  Feature count:   {l_stats['count']}")
        print(f"  Geometry types:  {l_stats['geom_types']}")
        print(f"  Vertex counts -> Min: {l_stats['min_vertices']}, Median: {l_stats['median_vertices']:.1f}, Max: {l_stats['max_vertices']}")

    summary = {
        "event_date": event_date,
        "snapshot_time": snapshot_time,
        "base_bbox": bbox,
        "buffered_bbox": buf_bbox,
        "buffer_km": buffer_km,
        "layer_stats": stats
    }

    with open(summary_file, "w") as f:
        json.dump(summary, f, indent=2)

    return summary


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Fetch buffered OSM for L5 routing")
    parser.add_argument("--bbox", type=float, nargs=4, required=True, help="W S E N")
    parser.add_argument("--event-date", type=str, required=True, help="YYYY-MM-DD")
    parser.add_argument("--buffer-km", type=float, default=30.0)
    parser.add_argument("--utm-crs", type=str, default="auto")
    args = parser.parse_args()
    fetch_buffered_osm(
        bbox=args.bbox,
        buffer_km=args.buffer_km,
        event_date=args.event_date,
        utm_crs=args.utm_crs
    )
