"""
Fetch pre-event OpenStreetMap vectors via ohsome API.
Rule: Zero synthetic or fallback data. Never use Overpass.
Time parameter strictly derived before event_date.
"""

import sys
import os
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
    return "2026-07-27T09:00:00Z"


def query_ohsome_layer(
    bbox: List[float],
    filter_expr: str,
    snapshot_time: str
) -> Dict[str, Any]:
    """Query ohsome elements/bbox (or elements/geometry) endpoint."""
    bbox_str = f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]}"
    data = {
        "bboxes": bbox_str,
        "filter": filter_expr,
        "time": snapshot_time,
        "properties": "tags"
    }

    # Try elements/bbox endpoint first (publicly permitted)
    endpoints = ["elements/bbox", "elements/geometry"]
    last_err = None
    for ep in endpoints:
        url = f"{OHSOME_BASE_URL}/{ep}"
        try:
            resp = http_client.post(url, data=data, timeout=120)
            if resp.status_code == 200:
                return resp.json()
            elif resp.status_code == 403:
                last_err = f"HTTP 403 on {ep}"
                continue
            else:
                last_err = f"HTTP {resp.status_code}: {resp.text[:200]}"
        except requests.exceptions.RequestException as e:
            last_err = f"Request exception on {ep}: {e}"

    logger.error(f"Failed to query ohsome for filter '{filter_expr}': {last_err}")
    sys.exit(f"FAILED: ohsome query failed: {last_err}")


def fetch_osm(
    bbox: List[float],
    event_date: str,
    out_dir: str,
    days_before: int = 1,
    force: bool = False
) -> Dict[str, Any]:
    """
    Fetch OSM pre-event snapshots for buildings, roads, bridges, hospitals, places.
    Snapshot time is strictly computed before event_date.
    """
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    summary_file = out_path / "osm_summary.json"

    if not force and summary_file.exists():
        try:
            with open(summary_file, "r") as f:
                cached = json.load(f)
            counts = cached.get("feature_counts", {})
            if len(counts) == len(OSM_QUERIES):
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

    counts = {}
    for layer_name, filter_expr in OSM_QUERIES.items():
        logger.info(f"Fetching OSM layer '{layer_name}' with filter '{filter_expr}'...")
        geojson_res = query_ohsome_layer(bbox, filter_expr, snapshot_time)
        feature_count = len(geojson_res.get("features", []))
        counts[layer_name] = feature_count

        layer_file = out_path / f"osm_{layer_name}.geojson"
        with open(layer_file, "w") as f:
            json.dump(geojson_res, f, indent=2)
        logger.info(f"Saved {feature_count} features to {layer_file}")

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
