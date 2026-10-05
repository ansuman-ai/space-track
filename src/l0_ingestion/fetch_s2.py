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
    s2_scene_timeout_s: float = 40.0,
    s2_total_budget_s: float = 120.0,
    force: bool = False
) -> Dict[str, Any]:
    """
    Ingests Sentinel-2 L2A scenes for pre, post, control, and seasonal analysis.
    Enforces s2_max_scenes, s2_search_timeout_s, hard per-scene timeout (s2_scene_timeout_s),
    and total S2 download time budget (s2_total_budget_s).
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

    # Sort post_feats ASCENDING by datetime (earliest after event) before slicing s2_max_scenes
    post_feats = sorted(post_feats, key=lambda x: x.get("properties", {}).get("datetime", ""))
    if len(post_feats) > s2_max_scenes:
        logger.info(f"S2 extended post search hit limit s2_max_scenes={s2_max_scenes}; using {s2_max_scenes} earliest scenes found.")
        post_feats = post_feats[:s2_max_scenes]
    else:
        logger.info(f"Found {len(post_feats)} post-event S2 scenes.")

    pre_feats = search_s2_stac(bbox, pre_start, pre_end, timeout_s=s2_search_timeout_s)
    pre_feats = sorted(pre_feats, key=lambda x: x.get("properties", {}).get("datetime", ""), reverse=True)
    if len(pre_feats) > s2_max_scenes:
        pre_feats = pre_feats[:s2_max_scenes]

    ctrl_feats = search_s2_stac(bbox, ctrl_start, ctrl_end, timeout_s=s2_search_timeout_s)
    ctrl_feats = sorted(ctrl_feats, key=lambda x: x.get("properties", {}).get("datetime", ""), reverse=True)
    if len(ctrl_feats) > s2_max_scenes:
        ctrl_feats = ctrl_feats[:s2_max_scenes]

    seas_pre_feats = search_s2_stac(bbox, seas_pre_start, seas_pre_end, timeout_s=s2_search_timeout_s)
    seas_pre_feats = sorted(seas_pre_feats, key=lambda x: x.get("properties", {}).get("datetime", ""), reverse=True)

    seas_post_feats = search_s2_stac(bbox, seas_post_start, seas_post_end, timeout_s=s2_search_timeout_s)
    seas_post_feats = sorted(seas_post_feats, key=lambda x: x.get("properties", {}).get("datetime", ""))

    logger.info(f"S2 search completed in {round(time.time() - t_search_0, 2)}s: "
                f"pre={len(pre_feats)}, post={len(post_feats)}, ctrl={len(ctrl_feats)}, "
                f"seas_pre={len(seas_pre_feats)}, seas_post={len(seas_post_feats)}")

    from .gdal_env import get_shared_gdal_env
    # Token retrieval
    token = get_s2_sas_token()
    env = get_shared_gdal_env()

    # Determine reference bounds and shape from bbox in UTM
    from rasterio.warp import transform_bounds
    utm_bounds = transform_bounds("EPSG:4326", utm_crs, *bbox)
    target_width = int(round((utm_bounds[2] - utm_bounds[0]) / 10.0))
    target_height = int(round((utm_bounds[3] - utm_bounds[1]) / 10.0))
    target_shape = (target_height, target_width)

    def _get_orbit_str(feat):
        props = feat.get("properties", {})
        orbit = props.get("sat:relative_orbit") or props.get("s2:relative_orbit", "")
        return f"R{orbit:03d}" if isinstance(orbit, int) else (f"R{orbit}" if orbit else "R000")

    # Select best scenes per orbit in priority order (post, then pre, then ctrl, then seas)
    selected_scenes_to_fetch = []

    # 1. Post: sort ascending by datetime (earliest after event), pick up to 2 per orbit
    post_by_orb = {}
    for f in post_feats:
        orb = _get_orbit_str(f)
        post_by_orb.setdefault(orb, []).append(f)
    for orb, f_list in post_by_orb.items():
        for f in f_list[:2]:
            selected_scenes_to_fetch.append(("post", f))

    # 2. Pre: sort descending by datetime (closest to event), pick 1 per orbit
    pre_by_orb = {}
    for f in pre_feats:
        orb = _get_orbit_str(f)
        if orb not in pre_by_orb:
            pre_by_orb[orb] = f
            selected_scenes_to_fetch.append(("pre", f))

    # 3. Ctrl: sort descending by datetime (closest to pre window), pick 1 per orbit
    ctrl_by_orb = {}
    for f in ctrl_feats:
        orb = _get_orbit_str(f)
        if orb not in ctrl_by_orb:
            ctrl_by_orb[orb] = f
            selected_scenes_to_fetch.append(("ctrl", f))

    # 4. Seasonal pre: pick 1 per orbit
    seas_pre_by_orb = {}
    for f in seas_pre_feats:
        orb = _get_orbit_str(f)
        if orb not in seas_pre_by_orb:
            seas_pre_by_orb[orb] = f
            selected_scenes_to_fetch.append(("seas_pre", f))

    # 5. Seasonal post: pick 1 per orbit
    seas_post_by_orb = {}
    for f in seas_post_feats:
        orb = _get_orbit_str(f)
        if orb not in seas_post_by_orb:
            seas_post_by_orb[orb] = f
            selected_scenes_to_fetch.append(("seas_post", f))

    import concurrent.futures

    def _fetch_scene_bands(item_tuple):
        prefix, feat = item_tuple
        scene_id = feat.get("id", "")
        props = feat.get("properties", {})
        orbit_str = _get_orbit_str(feat)

        save_fn = out_path / f"{prefix}_{orbit_str}_{scene_id[:30]}.npz"
        if save_fn.exists():
            return save_fn.name

        assets = feat.get("assets", {})
        sun_elev = float(props.get("view:sun_elevation", 65.0))
        sun_az = float(props.get("view:sun_azimuth", 135.0))

        band_names = ['B02', 'B03', 'B04', 'B08', 'B11', 'B12', 'SCL', 'visual']

        def _read_band(b_name):
            b_src = 'B11' if b_name == 'B12' and 'B12' not in assets and 'B11' in assets else b_name
            if b_src not in assets:
                return None, None
            url = assets[b_src]['href']
            if token and "?" not in url:
                url = f"{url}?{token}"
            for attempt in range(2):
                with env:
                    try:
                        with rasterio.open(url) as s:
                            b_s = transform_bounds(utm_crs, s.crs, *utm_bounds) if s.crs.to_string() != utm_crs else utm_bounds
                            w = from_bounds(*b_s, transform=s.transform)
                            out_s = (3, *target_shape) if b_name == 'visual' else target_shape
                            arr = s.read(window=w, out_shape=out_s)
                            if b_name != 'visual' and arr.ndim == 3 and arr.shape[0] == 1:
                                arr = arr[0]
                            return b_name, arr
                    except Exception as e:
                        if attempt == 0:
                            time.sleep(1)
                            continue
                        logger.warning(f"Error reading band {b_name} for {scene_id}: {e}")
                        return None, None

        bands = {
            "sun_elevation": np.array(sun_elev, dtype=np.float32),
            "sun_azimuth": np.array(sun_az, dtype=np.float32)
        }

        b_ex = concurrent.futures.ThreadPoolExecutor(max_workers=4)
        try:
            futs = [b_ex.submit(_read_band, b) for b in band_names]
            for fut in futs:
                try:
                    k, v = fut.result(timeout=s2_scene_timeout_s)
                    if k is not None and v is not None:
                        bands[k] = v
                except concurrent.futures.TimeoutError:
                    logger.warning(f"Planetary Computer slow/hanging on band read for scene {scene_id[:30]}.")
        finally:
            b_ex.shutdown(wait=False, cancel_futures=True)

        if "B04" in bands and "B08" in bands:
            if "visual" not in bands and "B03" in bands and "B02" in bands:
                r, g, b = bands["B04"], bands["B03"], bands["B02"]
                bands["visual"] = np.clip(np.stack([r, g, b], axis=0) / 3000.0 * 255.0, 0, 255).astype(np.uint8)
            np.savez_compressed(save_fn, **bands)
            logger.info(f"Saved S2 scene to {save_fn.name}")
            return save_fn.name
        return None

    t0_download = time.time()
    all_downloaded = []
    skipped_scenes = []

    sc_ex = concurrent.futures.ThreadPoolExecutor(max_workers=2)
    try:
        sc_futs = {}
        for item in selected_scenes_to_fetch:
            elapsed = time.time() - t0_download
            if elapsed >= s2_total_budget_s:
                sc_id = item[1].get("id", "unknown")
                logger.warning(
                    f"[S2_BUDGET] Planetary Computer S2 total budget ({s2_total_budget_s:.1f}s) exceeded (elapsed: {elapsed:.1f}s). "
                    f"Stopping downloads. Skipping remaining scene: {sc_id[:35]}"
                )
                skipped_scenes.append({"scene_id": sc_id, "reason": "budget_exceeded"})
                continue

            fut = sc_ex.submit(_fetch_scene_bands, item)
            sc_futs[fut] = item[1].get("id", "unknown")

        for fut in list(sc_futs.keys()):
            elapsed = time.time() - t0_download
            remaining_budget = max(0.1, s2_total_budget_s - elapsed)
            wait_timeout = min(s2_scene_timeout_s, remaining_budget)
            sc_id = sc_futs[fut]
            try:
                res_fn = fut.result(timeout=wait_timeout)
                if res_fn:
                    all_downloaded.append(res_fn)
                else:
                    skipped_scenes.append({"scene_id": sc_id, "reason": "missing_critical_bands"})
            except concurrent.futures.TimeoutError:
                logger.warning(
                    f"[S2_TIMEOUT] Planetary Computer scene download timed out after {wait_timeout:.1f}s. "
                    f"Skipping scene: {sc_id[:35]}"
                )
                skipped_scenes.append({"scene_id": sc_id, "reason": "timeout"})
            except Exception as e:
                logger.warning(f"Error fetching scene {sc_id[:35]}: {e}")
                skipped_scenes.append({"scene_id": sc_id, "reason": str(e)})
    finally:
        sc_ex.shutdown(wait=False, cancel_futures=True)

    budget_hit = (time.time() - t0_download >= s2_total_budget_s)
    if budget_hit:
        logger.warning(
            f"[S2_BUDGET] Planetary Computer S2 total budget ({s2_total_budget_s:.1f}s) triggered. "
            f"Total scenes downloaded: {len(all_downloaded)}, skipped: {len(skipped_scenes)}."
        )

    return {
        "status": "FETCHED",
        "scene_count": len(all_downloaded),
        "scenes": all_downloaded,
        "skipped_scenes": skipped_scenes,
        "budget_exceeded": budget_hit
    }
