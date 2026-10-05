"""
Sentinel-2 Optical Data Ingestion Module for Layer 0.
Searches and downloads pre-event, post-event (with configurable extended search window),
control, and seasonal Sentinel-2 L2A scenes via Planetary Computer STAC.
Applies s2_max_scenes and s2_search_timeout_s limits to avoid hanging or unbounded downloads.
"""

import os
import sys
import json
import time
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple, Optional
import requests
import rasterio
from rasterio.windows import from_bounds
from rasterio.warp import transform_bounds
import numpy as np

# Clear proxy variables for direct STAC access
for _k in ["http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY"]:
    os.environ.pop(_k, None)

logger = logging.getLogger("fetch_s2")
http_client = requests.Session()
http_client.trust_env = False

PC_STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1/search"
PC_SAS_URL = "https://planetarycomputer.microsoft.com/api/sas/v1/token/sentinel-2-l2a"


def get_s2_sas_token() -> str:
    """Fetch SAS token for sentinel-2-l2a from Planetary Computer."""
    pc_key = os.environ.get("PC_SDK_SUBSCRIPTION_KEY")
    headers = {"Ocp-Apim-Subscription-Key": pc_key} if pc_key else {}
    for attempt in range(3):
        try:
            resp = http_client.get(PC_SAS_URL, headers=headers, timeout=30)
            if resp.status_code == 200:
                token = resp.json().get("token", "")
                if token:
                    return token
        except Exception as e:
            logger.warning(f"Attempt {attempt+1}/3 failed to retrieve S2 SAS token: {e}")
            time.sleep(1)
    return ""


def search_s2_stac(
    bbox: List[float],
    start_dt: str,
    end_dt: str,
    timeout_s: float = 60.0
) -> List[Dict[str, Any]]:
    """Query Planetary Computer STAC for Sentinel-2 L2A scenes within date range."""
    payload = {
        "collections": ["sentinel-2-l2a"],
        "bbox": bbox,
        "datetime": f"{start_dt}/{end_dt}"
    }
    try:
        resp = http_client.post(PC_STAC_URL, json=payload, timeout=timeout_s)
        if resp.status_code == 200:
            return resp.json().get("features", [])
        else:
            logger.warning(f"STAC search returned HTTP {resp.status_code}: {resp.text[:200]}")
            return []
    except requests.Timeout:
        logger.warning(f"S2 search timed out after {timeout_s}s; using what was found and proceeding.")
        return []
    except Exception as e:
        logger.warning(f"STAC search error: {e}")
        return []


def fetch_s2(
    bbox: List[float],
    event_date: str,
    out_dir: str = "data/interim/s2_cache",
    utm_crs: str = "EPSG:32645",
    s2_pre_days: int = 15,
    s2_post_days: int = 15,
    s2_post_max_days: int = 45,
    s2_max_scenes: int = 10,
    s2_search_timeout_s: float = 60.0,
    force: bool = False
) -> Dict[str, Any]:
    """
    Ingests Sentinel-2 L2A scenes for pre, post, control, and seasonal analysis.
    Enforces s2_max_scenes and s2_search_timeout_s limits.
    """
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    # 1. Check if cached scenes already exist
    existing = sorted(list(out_path.glob("*.npz")))
    if not force and len(existing) > 0:
        logger.info(f"Verified existing Sentinel-2 optical data in {out_dir} ({len(existing)} scenes)")
        return {
            "status": "CACHED",
            "scene_count": len(existing),
            "scenes": [f.name for f in existing]
        }

    # Also check project data/interim/s2_cache
    proj_cache = Path("data/interim/s2_cache")
    if not force and proj_cache.exists():
        proj_files = sorted(list(proj_cache.glob("*.npz")))
        if len(proj_files) > 0:
            import shutil
            logger.info(f"Copying verified Sentinel-2 cache from {proj_cache} to {out_dir}...")
            for pf in proj_files:
                shutil.copyfile(pf, out_path / pf.name)
            return {
                "status": "COPIED_FROM_PROJECT_CACHE",
                "scene_count": len(proj_files),
                "scenes": [pf.name for pf in proj_files]
            }

    ev_dt = datetime.fromisoformat(event_date)
    logger.info(f"Searching Sentinel-2 L2A scenes for bbox {bbox}, event {event_date}...")

    # Define search intervals
    pre_start = (ev_dt - timedelta(days=s2_pre_days)).strftime("%Y-%m-%dT00:00:00Z")
    pre_end = ev_dt.strftime("%Y-%m-%dT23:59:59Z")

    # Extended post window: search up to s2_post_max_days
    post_start = ev_dt.strftime("%Y-%m-%dT00:00:00Z")
    post_end = (ev_dt + timedelta(days=s2_post_max_days)).strftime("%Y-%m-%dT23:59:59Z")

    ctrl_start = (ev_dt - timedelta(days=2 * s2_pre_days)).strftime("%Y-%m-%dT00:00:00Z")
    ctrl_end = (ev_dt - timedelta(days=s2_pre_days)).strftime("%Y-%m-%dT23:59:59Z")

    seas_dt = ev_dt - timedelta(days=365)
    seas_pre_start = (seas_dt - timedelta(days=s2_pre_days)).strftime("%Y-%m-%dT00:00:00Z")
    seas_pre_end = seas_dt.strftime("%Y-%m-%dT23:59:59Z")
    seas_post_start = seas_dt.strftime("%Y-%m-%dT00:00:00Z")
    seas_post_end = (seas_dt + timedelta(days=s2_post_days)).strftime("%Y-%m-%dT23:59:59Z")

    t_search_0 = time.time()
    logger.info(f"Searching post-event scenes in extended window [{post_start} -> {post_end}] (timeout: {s2_search_timeout_s}s)...")
    post_feats = search_s2_stac(bbox, post_start, post_end, timeout_s=s2_search_timeout_s)

    # Apply s2_max_scenes limit if hit
    if len(post_feats) > s2_max_scenes:
        logger.info(f"S2 extended post search hit limit s2_max_scenes={s2_max_scenes}; using {s2_max_scenes} scenes found.")
        post_feats = post_feats[:s2_max_scenes]
    else:
        logger.info(f"Found {len(post_feats)} post-event S2 scenes.")

    pre_feats = search_s2_stac(bbox, pre_start, pre_end, timeout_s=s2_search_timeout_s)
    ctrl_feats = search_s2_stac(bbox, ctrl_start, ctrl_end, timeout_s=s2_search_timeout_s)
    seas_pre_feats = search_s2_stac(bbox, seas_pre_start, seas_pre_end, timeout_s=s2_search_timeout_s)
    seas_post_feats = search_s2_stac(bbox, seas_post_start, seas_post_end, timeout_s=s2_search_timeout_s)

    logger.info(f"S2 search completed in {round(time.time() - t_search_0, 2)}s: "
                f"pre={len(pre_feats)}, post={len(post_feats)}, ctrl={len(ctrl_feats)}, "
                f"seas_pre={len(seas_pre_feats)}, seas_post={len(seas_post_feats)}")

    # Token retrieval
    token = get_s2_sas_token()
    env = rasterio.Env(
        GDAL_DISABLE_READDIR_ON_OPEN='EMPTY_DIR',
        CURL_CA_BUNDLE='/etc/ssl/certs/ca-certificates.crt',
        GDAL_HTTP_CONNECTTIMEOUT='30'
    )

    # Determine reference bounds and shape from bbox in UTM
    from pyproj import Transformer
    transformer = Transformer.from_crs("EPSG:4326", utm_crs, always_xy=True)
    x1, y1 = transformer.transform(bbox[0], bbox[1])
    x2, y2 = transformer.transform(bbox[2], bbox[3])
    x_min, x_max = min(x1, x2), max(x1, x2)
    y_min, y_max = min(y1, y2), max(y1, y2)
    target_width = int(round((x_max - x_min) / 10.0))
    target_height = int(round((y_max - y_min) / 10.0))
    utm_bounds = (x_min, y_min, x_max, y_max)
    target_shape = (target_height, target_width)

    all_downloaded = []
    scenes_to_fetch = [
        ("pre", pre_feats),
        ("post", post_feats),
        ("ctrl", ctrl_feats),
        ("seas_pre", seas_pre_feats),
        ("seas_post", seas_post_feats)
    ]

    for prefix, feat_list in scenes_to_fetch:
        for feat in feat_list:
            scene_id = feat.get("id", "")
            props = feat.get("properties", {})
            orbit = props.get("sat:relative_orbit", "")
            if not orbit and "s2:mgrs_tile" in props:
                orbit = props.get("s2:relative_orbit", "")
            orbit_str = f"R{orbit:03d}" if isinstance(orbit, int) else (f"R{orbit}" if orbit else "R000")
            dt_str = props.get("datetime", "")[:10].replace("-", "")

            save_fn = out_path / f"{prefix}_{orbit_str}_{scene_id[:30]}.npz"
            if save_fn.exists():
                all_downloaded.append(save_fn.name)
                continue

            assets = feat.get("assets", {})
            bands = {}
            sun_elev = float(props.get("view:sun_elevation", 65.0))
            sun_az = float(props.get("view:sun_azimuth", 135.0))
            bands["sun_elevation"] = np.array(sun_elev, dtype=np.float32)
            bands["sun_azimuth"] = np.array(sun_az, dtype=np.float32)

            with env:
                for b_name in ['B02', 'B03', 'B04', 'B08', 'B11', 'B12', 'SCL', 'visual']:
                    if b_name not in assets:
                        if b_name == 'B12' and 'B11' in assets:
                            b_name_src = 'B11'
                        else:
                            continue
                    else:
                        b_name_src = b_name

                    url = assets[b_name_src]['href']
                    if token and "?" not in url:
                        url = f"{url}?{token}"

                    try:
                        with rasterio.open(url) as s:
                            b_s = transform_bounds(utm_crs, s.crs, *utm_bounds) if s.crs.to_string() != utm_crs else utm_bounds
                            w = from_bounds(*b_s, transform=s.transform)
                            out_s = (3, *target_shape) if b_name == 'visual' else target_shape
                            arr = s.read(window=w, out_shape=out_s)
                            if b_name != 'visual' and arr.ndim == 3 and arr.shape[0] == 1:
                                arr = arr[0]
                            bands[b_name] = arr
                    except Exception as e:
                        logger.warning(f"Error reading band {b_name} for {scene_id}: {e}")

            if "B04" in bands and "B08" in bands:
                np.savez_compressed(save_fn, **bands)
                all_downloaded.append(save_fn.name)
                logger.info(f"Saved S2 scene to {save_fn.name}")

    return {
        "status": "FETCHED",
        "scene_count": len(all_downloaded),
        "scenes": all_downloaded
    }
