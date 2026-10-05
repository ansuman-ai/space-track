"""
Fetch pre-event OpenStreetMap vectors via ohsome API.
Rule: Zero synthetic or fallback data. Never use Overpass.
Time parameter strictly derived before event_date.
"""

import sys
import os
import time
import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("fetch_osm")

http_client = requests.Session()
http_client.trust_env = False
http_client.headers.update({
    "User-Agent": "FloodDamageAssessment/1.0 (GIS research; contact@hackathon.org)"
})

OHSOME_BASE_URL = "https://api.ohsome.org/v1"

OSM_QUERIES = {
    "waterways": "(waterway=* or natural=water) and (geometry:line or geometry:polygon)",
    "roads": "highway=* and highway!=footway and highway!=path and highway!=steps and highway!=cycleway and geometry:line",
    "bridges": "bridge=* and bridge!=no and geometry:line",
    "buildings": "building=* and geometry:polygon",
    "hospitals": "(amenity=hospital or amenity=clinic or amenity=doctors or healthcare=hospital) and (geometry:point or geometry:polygon)",
    "places": "(place=city or place=town or place=village or place=hamlet or place=isolated_dwelling) and geometry:point"
}


def get_latest_ohsome_timestamp() -> str:
    """Fetch maximum available timestamp from ohsome API metadata."""
    try:
        resp = http_client.get(f"{OHSOME_BASE_URL}/metadata", timeout=15)
        if resp.status_code == 200:
            to_ts = resp.json().get("extractRegion", {}).get("temporalExtent", {}).get("toTimestamp")
            if to_ts:
                return to_ts
    except Exception as e:
        logger.warning(f"Could not query ohsome metadata: {e}")
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")


import concurrent.futures

def query_ohsome_layer(
    bbox: List[float],
    filter_expr: str,
    snapshot_time: str
) -> Dict[str, Any]:
    """Query ohsome geometry extraction endpoint via elementsFullHistory/geometry with pre-event interval."""
    bbox_str = f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]}"
    
    t_end = datetime.fromisoformat(snapshot_time.replace("Z", "+00:00"))
    t_start = (t_end - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    time_interval = f"{t_start},{snapshot_time}"
    
    data_hist = {
        "bboxes": bbox_str,
        "filter": filter_expr,
        "time": time_interval,
        "properties": "tags,metadata"
    }
    url_hist = f"{OHSOME_BASE_URL}/elementsFullHistory/geometry"
    for attempt in range(3):
        try:
            resp = http_client.post(url_hist, data=data_hist, timeout=300)
            if resp.status_code == 200:
                res = resp.json()
                feats = res.get("features", [])
                # Deduplicate by @osmId keeping latest version
                dedup = {}
                for f in feats:
                    oid = f.get("properties", {}).get("@osmId")
                    ver = f.get("properties", {}).get("@version", 0)
                    if oid not in dedup or ver > dedup[oid].get("properties", {}).get("@version", 0):
                        dedup[oid] = f
                res["features"] = list(dedup.values())
                return res
            elif resp.status_code >= 500:
                time.sleep(2)
                continue
            else:
                logger.error(f"elementsFullHistory/geometry failed: {resp.status_code} - {resp.text[:200]}")
                sys.exit(f"FAILED: ohsome geometry query failed: {resp.status_code}")
        except requests.exceptions.RequestException as e:
            if attempt == 2:
                sys.exit(f"FAILED: ohsome network error: {e}")
            time.sleep(2)


def match_waterways(f: Dict[str, Any]) -> bool:
    props = f.get("properties", {})
    gtype = f.get("geometry", {}).get("type", "")
    is_geom = gtype in ("LineString", "MultiLineString", "Polygon", "MultiPolygon")
    has_tag = bool(props.get("waterway")) or (props.get("natural") == "water")
    return is_geom and has_tag


def match_roads(f: Dict[str, Any]) -> bool:
    props = f.get("properties", {})
    gtype = f.get("geometry", {}).get("type", "")
    is_geom = gtype in ("LineString", "MultiLineString")
    hw = props.get("highway")
    return is_geom and bool(hw) and hw not in ("footway", "path", "steps", "cycleway")


def match_bridges(f: Dict[str, Any]) -> bool:
    props = f.get("properties", {})
    gtype = f.get("geometry", {}).get("type", "")
    is_geom = gtype in ("LineString", "MultiLineString")
    br = props.get("bridge")
    return is_geom and bool(br) and br != "no"


def match_buildings(f: Dict[str, Any]) -> bool:
    props = f.get("properties", {})
    gtype = f.get("geometry", {}).get("type", "")
    is_geom = gtype in ("Polygon", "MultiPolygon")
    return is_geom and bool(props.get("building"))


def match_hospitals(f: Dict[str, Any]) -> bool:
    props = f.get("properties", {})
    gtype = f.get("geometry", {}).get("type", "")
    is_geom = gtype in ("Point", "MultiPoint", "Polygon", "MultiPolygon")
    am = props.get("amenity")
    hc = props.get("healthcare")
    return is_geom and (am in ("hospital", "clinic", "doctors") or hc == "hospital")


def match_places(f: Dict[str, Any]) -> bool:
    props = f.get("properties", {})
    gtype = f.get("geometry", {}).get("type", "")
    is_geom = gtype in ("Point", "MultiPoint")
    pl = props.get("place")
    return is_geom and pl in ("city", "town", "village", "hamlet", "isolated_dwelling")


LAYER_MATCHERS = {
    "waterways": match_waterways,
    "roads": match_roads,
    "bridges": match_bridges,
    "buildings": match_buildings,
    "hospitals": match_hospitals,
    "places": match_places,
}


def fetch_osm(
    bbox: List[float],
    event_date: str,
    out_dir: str,
    days_before: int = 1,
    force: bool = False
) -> Dict[str, Any]:
    """
    Fetch OSM pre-event snapshots for buildings, roads, bridges, hospitals, places.
    Uses a single combined ohsome query and splits features locally by tags.
    """
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    summary_file = out_path / "osm_summary.json"

    if not force and summary_file.exists():
        try:
            with open(summary_file, "r") as f:
                cached = json.load(f)
            counts = cached.get("feature_counts", {})
            if len(counts) == len(OSM_QUERIES) and all((out_path / f"osm_{k}.geojson").exists() for k in OSM_QUERIES):
                logger.info(f"Verified existing OSM layers in {out_dir} (counts: {counts})")
                return cached
        except Exception:
            logger.warning("Existing OSM summary corrupted; refetching...")

    ev_dt = datetime.fromisoformat(event_date)
    pre_event_dt = (ev_dt - timedelta(days=days_before)).strftime("%Y-%m-%dT00:00:00Z")

    # Clamp to latest available timestamp in ohsome if necessary
    latest_ts = get_latest_ohsome_timestamp()
    snapshot_time = min(pre_event_dt, latest_ts)

    logger.info(f"Using pre-event OSM snapshot timestamp: {snapshot_time} for bbox: {bbox}")

    combined_filter = " or ".join(f"({v})" for v in OSM_QUERIES.values())
    logger.info("Executing single combined ohsome geometry extraction query for all bbox layers...")
    t_q0 = time.time()
    geojson_res = query_ohsome_layer(bbox, combined_filter, snapshot_time)
    t_q1 = time.time()
    all_features = geojson_res.get("features", [])
    logger.info(f"Combined OSM query returned {len(all_features)} total features in {t_q1 - t_q0:.2f}s")

    counts = {}
    for layer_name, matcher in LAYER_MATCHERS.items():
        layer_feats = [f for f in all_features if matcher(f)]
        layer_file = out_path / f"osm_{layer_name}.geojson"
        layer_res = {
            "attribution": geojson_res.get("attribution", {}),
            "apiVersion": geojson_res.get("apiVersion", ""),
            "type": "FeatureCollection",
            "features": layer_feats
        }
        with open(layer_file, "w") as f:
            json.dump(layer_res, f, indent=2)
        counts[layer_name] = len(layer_feats)
        logger.info(f"Saved {len(layer_feats)} features to {layer_file}")

    summary = {
        "event_date": event_date,
        "snapshot_time": snapshot_time,
        "bbox": bbox,
        "feature_counts": counts
    }

    summary_file = out_path / "osm_summary.json"
    with open(summary_file, "w") as f:
        json.dump(summary, f, indent=2)

    return summary


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Fetch pre-event OSM via ohsome API")
    parser.add_argument("--bbox", type=float, nargs=4, required=True, help="min_lon min_lat max_lon max_lat")
    parser.add_argument("--event-date", type=str, required=True, help="YYYY-MM-DD")
    parser.add_argument("--out-dir", type=str, required=True, help="Output directory")
    args = parser.parse_args()

    fetch_osm(args.bbox, args.event_date, args.out_dir)
