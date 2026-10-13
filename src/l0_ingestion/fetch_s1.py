"""
Fetch Sentinel-1 RTC pre/post pair for a given bbox and event date.
Rule: Zero synthetic or fallback data. Exit FAILED with exact error on failure.
"""

import sys
import os
import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple, Optional
import requests
import rasterio
from rasterio.windows import from_bounds
from rasterio.enums import Resampling
import numpy as np
import concurrent.futures

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("fetch_s1")
import time

# Ensure proxy does not interfere with GDAL/requests direct calls
for _k in ["http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY"]:
    os.environ.pop(_k, None)

http_client = requests.Session()
http_client.trust_env = False

PC_STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1/search"
PC_SAS_URL = "https://planetarycomputer.microsoft.com/api/sas/v1/sign"
CDSE_STAC_URL = "https://catalogue.dataspace.copernicus.eu/stac/search"


def get_sas_token(collection: str = "sentinel-1-rtc") -> str:
    """Fetch SAS token for collection from Planetary Computer."""
    pc_key = os.environ.get("PC_SDK_SUBSCRIPTION_KEY")
    headers = {"Ocp-Apim-Subscription-Key": pc_key} if pc_key else {}
    for attempt in range(3):
        try:
            resp = http_client.get(f"https://planetarycomputer.microsoft.com/api/sas/v1/token/{collection}", headers=headers, timeout=60)
            if resp.status_code == 200:
                token = resp.json().get("token", "")
                if token:
                    return token
        except Exception as e:
            logger.warning(f"Attempt {attempt+1}/3 failed to retrieve SAS token for {collection}: {e}")
            time.sleep(2)
    logger.error(f"Failed to retrieve valid SAS token for {collection} after 3 attempts.")
    return ""


def sign_url(url: str, token: str) -> str:
    """Append SAS token to URL if not already present."""
    if not token or "?" in url:
        return url
    return f"{url}?{token}"


def query_stac(
    bbox: List[float],
    start_dt: str,
    end_dt: str,
    collection: str = "sentinel-1-rtc"
) -> List[Dict[str, Any]]:
    """Query Planetary Computer STAC API for Sentinel-1 scenes."""
    body = {
        "collections": [collection],
        "bbox": bbox,
        "datetime": f"{start_dt}/{end_dt}",
        "limit": 100
    }
    headers = {"Content-Type": "application/json"}
    pc_key = os.environ.get("PC_SDK_SUBSCRIPTION_KEY")
    if pc_key:
        headers["Ocp-Apim-Subscription-Key"] = pc_key

    resp = None
    for attempt in range(3):
        try:
            resp = http_client.post(PC_STAC_URL, json=body, headers=headers, timeout=20)
            break
        except requests.exceptions.RequestException as e:
            if attempt < 2:
                logger.warning(f"Attempt {attempt+1}/3 failed querying Planetary Computer STAC ({e}); retrying in 2s...")
                time.sleep(2)
                continue
            logger.error(f"Network error querying Planetary Computer STAC: {e}")
            raise RuntimeError(f"Network error querying STAC: {e}")

    if resp.status_code == 403:
        logger.error("HTTP 403 Forbidden: Sandbox or network environment blocked access to Planetary Computer STAC.")
        raise RuntimeError("HTTP 403 Forbidden when accessing Planetary Computer STAC API.")

    if resp.status_code != 200:
        logger.error(f"STAC search returned HTTP {resp.status_code}: {resp.text}")
        raise RuntimeError(f"STAC search returned HTTP {resp.status_code}: {resp.text}")

    features = resp.json().get("features", [])
    return features


def extract_metadata(item: Dict[str, Any]) -> Dict[str, Any]:
    """Extract standard properties from STAC item."""
    props = item.get("properties", {})
    rel_orbit = props.get("sat:relative_orbit") or props.get("sat:relative_orbit_number") or props.get("s1:relative_orbit_number")
    direction = props.get("sat:orbit_state") or props.get("s1:orbit_state")
    dt_str = props.get("datetime")
    return {
        "id": item.get("id"),
        "datetime": dt_str,
        "relative_orbit": rel_orbit,
        "orbit_direction": direction,
        "platform": props.get("platform"),
        "assets": item.get("assets", {})
    }


def download_and_clip_bands(
    item_meta: Dict[str, Any],
    bbox: List[float],
    out_path: Path,
    token: str = ""
) -> None:
    """Download VV and VH bands, clip to bbox (reprojected to native CRS), and save as 2-band GeoTIFF."""
    from rasterio.warp import transform_bounds

    assets = item_meta["assets"]
    vv_asset = assets.get("vv")
    vh_asset = assets.get("vh")

    if not vv_asset or not vh_asset:
        raise RuntimeError(f"Item {item_meta['id']} missing VV or VH asset")

    vv_url = sign_url(vv_asset["href"], token)
    vh_url = sign_url(vh_asset["href"], token)

    min_lon, min_lat, max_lon, max_lat = bbox

    from .gdal_env import get_shared_gdal_env
    try:
        env = get_shared_gdal_env(
            tag="Sentinel-1",
            GDAL_HTTP_VERSION="1.1",
            GDAL_HTTP_MULTIPLEX="NO",
            GDAL_HTTP_MERGE_CONSECUTIVE_RANGES="NO",
            CPL_VSIL_CURL_CHUNK_SIZE="1048576",
            GDAL_HTTP_TIMEOUT="60",
            GDAL_HTTP_CONNECTTIMEOUT="20",
            GDAL_HTTP_MAX_RETRY="2"
        )

        current_token = token

        def _read_band(raw_asset_href):
            nonlocal current_token
            last_err = None
            for attempt in range(5):
                # Prepare signed URL with current token
                base_u = raw_asset_href.split("?")[0] if "?" in raw_asset_href else raw_asset_href
                u = f"{base_u}?{current_token}" if current_token else raw_asset_href
                try:
                    with env:
                        with rasterio.open(u) as src:
                            if src.crs and src.crs.to_string() != "EPSG:4326":
                                proj_bounds = transform_bounds("EPSG:4326", src.crs, min_lon, min_lat, max_lon, max_lat)
                            else:
                                proj_bounds = (min_lon, min_lat, max_lon, max_lat)
                            window = from_bounds(*proj_bounds, transform=src.transform)
                            d = src.read(1, window=window)
                            out_trans = rasterio.windows.transform(window, src.transform)
                            meta = src.meta.copy()
                            return d, out_trans, meta
                except Exception as e:
                    last_err = e
                    sleep_s = 2 ** min(attempt, 3)
                    logger.warning(f"Attempt {attempt+1}/5 failed reading S1 band from Planetary Computer ({e}); refreshing SAS token and retrying in {sleep_s}s...")
                    # Refresh SAS token before retrying
                    fresh = get_sas_token("sentinel-1-rtc")
                    if fresh:
                        current_token = fresh
                    time.sleep(sleep_s)
            raise last_err

        # Fetch VV and VH sequentially to prevent Azure Blob rate-limiting / connection reset
        vv_data, out_transform, out_meta = _read_band(vv_asset["href"])
        vh_data, _, _ = _read_band(vh_asset["href"])

        out_meta.update({
            "driver": "GTiff",
            "height": vv_data.shape[0],
            "width": vv_data.shape[1],
            "transform": out_transform,
            "count": 2,
            "dtype": vv_data.dtype
        })

        with rasterio.open(out_path, "w", **out_meta) as dst:
            dst.write(vv_data, 1)
            dst.set_band_description(1, "VV")
            dst.write(vh_data, 2)
            dst.set_band_description(2, "VH")
            dst.update_tags(
                scene_id=item_meta["id"],
                datetime=item_meta["datetime"],
                relative_orbit=str(item_meta["relative_orbit"]),
                orbit_direction=str(item_meta["orbit_direction"])
            )

        logger.info(f"Saved clipped RTC raster to {out_path} ({vv_data.shape[1]}x{vv_data.shape[0]})")
    except Exception as e:
        logger.error(f"Failed to read/clip raster assets: {e}")
        raise RuntimeError(f"Could not download and clip S1 raster: {e}")


def check_bbox_overlap(item: Dict[str, Any], bbox: List[float], min_overlap: float = 0.90) -> Tuple[bool, float]:
    """Check if item footprint covers >= min_overlap of target bbox."""
    from shapely.geometry import shape, box
    if not item.get("geometry"):
        return False, 0.0
    try:
        item_geom = shape(item["geometry"])
        target_box = box(*bbox)
        if target_box.area <= 0:
            return True, 1.0
        overlap = float(item_geom.intersection(target_box).area / target_box.area)
        return overlap >= min_overlap, overlap
    except Exception as e:
        logger.warning(f"Error checking bbox overlap: {e}")
        return False, 0.0


def check_pair_bbox_overlap(item1: Dict[str, Any], item2: Dict[str, Any], bbox: List[float], min_overlap: float = 0.90) -> Tuple[bool, float]:
    """Check if the intersection of both items covers >= min_overlap of target bbox."""
    from shapely.geometry import shape, box
    if not item1.get("geometry") or not item2.get("geometry"):
        return False, 0.0
    try:
        g1 = shape(item1["geometry"])
        g2 = shape(item2["geometry"])
        target_box = box(*bbox)
        if target_box.area <= 0:
            return True, 1.0
        inter = g1.intersection(g2).intersection(target_box)
        overlap = float(inter.area / target_box.area)
        return overlap >= min_overlap, overlap
    except Exception as e:
        logger.warning(f"Error checking pair bbox overlap: {e}")
        return False, 0.0


def fetch_pair(
    bbox: List[float],
    event_date: str,
    out_dir: str,
    control_out_dir: Optional[str] = None,
    force: bool = False
) -> Tuple[Path, Path, Path]:
    """
    Fetch Sentinel-1 RTC pre/post pair and automatically fetch matched control pair.
    - post: first scene after event_date with >90% bbox overlap
    - pre: same relative orbit, direction, and overlapping frame (>90% overlap), 12 days earlier (fallback 24, 36)
    - control pair: same orbit and frame, 12 days before pre scene (>90% overlap).
      If missing or overlap < 90%: exit FAILED with an assertion/clear message.
    """
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    if control_out_dir is None:
        ctrl_path = out_path.parent.parent / "control" / "raw" / "s1"
    else:
        ctrl_path = Path(control_out_dir)
    ctrl_path.mkdir(parents=True, exist_ok=True)

    pre_tif = out_path / "pre.tif"
    post_tif = out_path / "post.tif"
    meta_json = out_path / "meta.json"

    ctrl_pre_tif = ctrl_path / "pre.tif"
    ctrl_post_tif = ctrl_path / "post.tif"
    ctrl_meta_json = ctrl_path / "meta.json"

    # Check if both event and control pairs are already verified
    if (not force and pre_tif.exists() and post_tif.exists() and meta_json.exists()
            and ctrl_pre_tif.exists() and ctrl_post_tif.exists() and ctrl_meta_json.exists()):
        try:
            with rasterio.open(pre_tif) as s1, rasterio.open(post_tif) as s2, \
                 rasterio.open(ctrl_pre_tif) as cs1, rasterio.open(ctrl_post_tif) as cs2:
                if s1.count == 2 and s2.count == 2 and cs1.count == 2 and cs2.count == 2:
                    logger.info(f"Verified existing Sentinel-1 event and control pairs in {out_dir} & {ctrl_path}")
                    return pre_tif, post_tif, meta_json
        except Exception:
            logger.warning("Existing S1 files corrupted; refetching...")

    ev_dt = datetime.fromisoformat(event_date)
    post_search_start = ev_dt.strftime("%Y-%m-%dT00:00:00Z")
    post_search_end = (ev_dt + timedelta(days=16)).strftime("%Y-%m-%dT23:59:59Z")

    logger.info(f"Querying STAC for post-event scene between {post_search_start} and {post_search_end}...")
    post_candidates = query_stac(bbox, post_search_start, post_search_end)

    if not post_candidates:
        raise RuntimeError(f"No Sentinel-1 scenes found after event date {event_date} for bbox {bbox}")

    post_candidates.sort(key=lambda x: x.get("properties", {}).get("datetime", ""))
    
    selected_post = None
    selected_post_item = None
    selected_pre = None
    selected_pre_item = None
    delta_used = None

    for candidate in post_candidates:
        cand_meta = extract_metadata(candidate)
        if not cand_meta["relative_orbit"] or not cand_meta["orbit_direction"]:
            continue
        
        ok_post, post_ov = check_bbox_overlap(candidate, bbox, min_overlap=0.90)
        if not ok_post:
            logger.info(f"Skipping post candidate {cand_meta['id']}: bbox overlap {post_ov*100:.1f}% < 90%")
            continue

        post_dt = datetime.fromisoformat(cand_meta["datetime"].replace("Z", "+00:00"))
        rel_orbit = cand_meta["relative_orbit"]
        direction = cand_meta["orbit_direction"]

        logger.info(f"Checking post candidate: {cand_meta['id']} ({cand_meta['datetime']}, orbit={rel_orbit}, dir={direction}, overlap={post_ov*100:.1f}%)")

        for lookback in [12, 24, 36]:
            target_pre_dt = post_dt - timedelta(days=lookback)
            pre_start = (target_pre_dt - timedelta(days=2)).strftime("%Y-%m-%dT00:00:00Z")
            pre_end = (target_pre_dt + timedelta(days=2)).strftime("%Y-%m-%dT23:59:59Z")

            pre_candidates = query_stac(bbox, pre_start, pre_end)
            for pre_cand in pre_candidates:
                pre_meta = extract_metadata(pre_cand)
                if (pre_meta["relative_orbit"] == rel_orbit and 
                    pre_meta["orbit_direction"] == direction):
                    ok_pre, pre_ov = check_bbox_overlap(pre_cand, bbox, min_overlap=0.90)
                    ok_pair, pair_ov = check_pair_bbox_overlap(candidate, pre_cand, bbox, min_overlap=0.90)
                    if not (ok_pre and ok_pair):
                        logger.info(f"Skipping pre candidate {pre_meta['id']}: mutual overlap {pair_ov*100:.1f}% < 90%")
                        continue
                    selected_post = cand_meta
                    selected_post_item = candidate
                    selected_pre = pre_meta
                    selected_pre_item = pre_cand
                    delta_used = lookback
                    break
            if selected_pre:
                break
        if selected_pre:
            break

    if selected_post is None or selected_pre is None:
        raise RuntimeError(
            f"Could not find matching same-orbit pre/post Sentinel-1 pair with >90% bbox overlap for event date {event_date} bbox {bbox}"
        )

    logger.info(f"Found matched event pair: Post={selected_post['id']} ({selected_post['datetime']}), Pre={selected_pre['id']} ({selected_pre['datetime']}), Orbit={selected_post['relative_orbit']}")

    # Now automatically find the CONTROL scene: same orbit, 12 days before the pre scene
    pre_dt = datetime.fromisoformat(selected_pre["datetime"].replace("Z", "+00:00"))
    ctrl_target_dt = pre_dt - timedelta(days=12)
    ctrl_search_start = (ctrl_target_dt - timedelta(days=2)).strftime("%Y-%m-%dT00:00:00Z")
    ctrl_search_end = (ctrl_target_dt + timedelta(days=2)).strftime("%Y-%m-%dT23:59:59Z")

    logger.info(f"Querying STAC for control scene (12 days prior to pre scene: {ctrl_target_dt.strftime('%Y-%m-%d')})...")
    ctrl_candidates = query_stac(bbox, ctrl_search_start, ctrl_search_end)

    selected_ctrl_pre = None
    for cand in ctrl_candidates:
        c_meta = extract_metadata(cand)
        if (c_meta["relative_orbit"] == selected_pre["relative_orbit"] and 
            c_meta["orbit_direction"] == selected_pre["orbit_direction"]):
            ok_c, c_ov = check_bbox_overlap(cand, bbox, min_overlap=0.90)
            ok_cp, cp_ov = check_pair_bbox_overlap(selected_pre_item, cand, bbox, min_overlap=0.90)
            if not (ok_c and ok_cp):
                continue
            selected_ctrl_pre = c_meta
            break

    if selected_ctrl_pre is None:
        raise RuntimeError(
            f"Missing Sentinel-1 control scene with >90% bbox overlap (same relative orbit {selected_pre['relative_orbit']} 12 days prior to pre-event scene)"
        )

    logger.info(f"Found matched control pre scene: {selected_ctrl_pre['id']} ({selected_ctrl_pre['datetime']})")

    token = get_sas_token("sentinel-1-rtc")

    # Download EVENT and CONTROL scenes sequentially to prevent Azure Blob rate-limiting
    logger.info("Downloading & clipping Sentinel-1 event (pre, post) and control scenes...")
    download_and_clip_bands(selected_pre, bbox, pre_tif, token)
    download_and_clip_bands(selected_post, bbox, post_tif, token)
    download_and_clip_bands(selected_ctrl_pre, bbox, ctrl_pre_tif, token)

    event_metadata_payload = {
        "event_date": event_date,
        "bbox": bbox,
        "post": {
            "id": selected_post["id"],
            "datetime": selected_post["datetime"],
            "relative_orbit": selected_post["relative_orbit"],
            "orbit_direction": selected_post["orbit_direction"],
            "platform": selected_post["platform"]
        },
        "pre": {
            "id": selected_pre["id"],
            "datetime": selected_pre["datetime"],
            "relative_orbit": selected_pre["relative_orbit"],
            "orbit_direction": selected_pre["orbit_direction"],
            "platform": selected_pre["platform"],
            "lookback_days": delta_used
        }
    }
    with open(meta_json, "w") as f:
        json.dump(event_metadata_payload, f, indent=2)

    import shutil
    shutil.copyfile(pre_tif, ctrl_post_tif)

    ctrl_metadata_payload = {
        "event_date": (pre_dt - timedelta(days=1)).strftime("%Y-%m-%d"),
        "bbox": bbox,
        "post": {
            "id": selected_pre["id"],
            "datetime": selected_pre["datetime"],
            "relative_orbit": selected_pre["relative_orbit"],
            "orbit_direction": selected_pre["orbit_direction"],
            "platform": selected_pre["platform"]
        },
        "pre": {
            "id": selected_ctrl_pre["id"],
            "datetime": selected_ctrl_pre["datetime"],
            "relative_orbit": selected_ctrl_pre["relative_orbit"],
            "orbit_direction": selected_ctrl_pre["orbit_direction"],
            "platform": selected_ctrl_pre["platform"],
            "lookback_days": 12
        }
    }
    with open(ctrl_meta_json, "w") as f:
        json.dump(ctrl_metadata_payload, f, indent=2)

    logger.info(f"Wrote event metadata to {meta_json} and control metadata to {ctrl_meta_json}")
    return pre_tif, post_tif, meta_json


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Fetch Sentinel-1 RTC pre/post pair")
    parser.add_argument("--bbox", type=float, nargs=4, required=True, help="min_lon min_lat max_lon max_lat")
    parser.add_argument("--event-date", type=str, required=True, help="YYYY-MM-DD")
    parser.add_argument("--out-dir", type=str, required=True, help="Output directory")
    args = parser.parse_args()

    fetch_pair(args.bbox, args.event_date, args.out_dir)
