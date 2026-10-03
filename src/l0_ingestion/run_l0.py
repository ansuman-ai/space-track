"""
Layer 0 Orchestrator: Ingests Sentinel-1 RTC pair, Copernicus DEM-30, and OSM pre-event snapshots.
"""

import sys
import argparse
from pathlib import Path
import yaml
import logging

from .fetch_s1 import fetch_pair
from .fetch_dem import fetch_dem
from .fetch_osm import fetch_osm

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("layer0_orchestrator")


def run_layer0(bbox, event_date, out_dir="data/raw", control_out_dir=None, buffer_km=10.0):
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    logger.info("=== LAYER 0: STARTING INGESTION ===")
    logger.info(f"Target BBOX: {bbox}")
    logger.info(f"Event Date: {event_date}")
    logger.info(f"Output Directory: {out_dir}")

    # Step 1: Sentinel-1 RTC pair + Control pair
    logger.info("--- Step 1/3: Fetching Sentinel-1 RTC pre/post pair & Control pair ---")
    s1_dir = out_path / "s1"
    pre_tif, post_tif, meta_json = fetch_pair(bbox, event_date, str(s1_dir), control_out_dir=control_out_dir)

    # Step 2: Copernicus DEM-30 (buffered)
    logger.info(f"--- Step 2/3: Fetching Copernicus DEM GLO-30 (buffer={buffer_km}km) ---")
    dem_dir = out_path / "dem"
    dem_tif = fetch_dem(bbox, str(dem_dir), buffer_km=buffer_km)

    # Step 3: OpenStreetMap Pre-Event Snapshot
    logger.info("--- Step 3/3: Fetching Pre-Event OSM from ohsome API ---")
    osm_dir = out_path / "osm"
    osm_summary = fetch_osm(bbox, event_date, str(osm_dir))

    logger.info("=== LAYER 0: INGESTION COMPLETE ===")
    return {
        "s1": {"pre": str(pre_tif), "post": str(post_tif), "meta": str(meta_json)},
        "dem": str(dem_tif),
        "osm": osm_summary
    }


def main():
    parser = argparse.ArgumentParser(description="Run Layer 0 Data Ingestion")
    parser.add_argument("--bbox", type=float, nargs=4, help="min_lon min_lat max_lon max_lat")
    parser.add_argument("--event-date", type=str, help="YYYY-MM-DD")
    parser.add_argument("--out-dir", type=str, default="data/raw", help="Output directory")
    parser.add_argument("--config", type=str, help="Path to test yaml config")

    args = parser.parse_args()

    if args.config:
        with open(args.config, "r") as f:
            cfg = yaml.safe_load(f)
        bbox = cfg["case_study"]["bbox"]
        event_date = cfg["case_study"]["event_date"]
    else:
        if not args.bbox or not args.event_date:
            sys.exit("Error: Must provide either --config or both --bbox and --event-date")
        bbox = args.bbox
        event_date = args.event_date

    run_layer0(bbox, event_date, args.out_dir)


if __name__ == "__main__":
    main()
