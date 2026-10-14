"""
Fetch Copernicus DEM GLO-30 for a given bounding box.
Rule: Zero synthetic or fallback data. Exit FAILED with exact error on failure.
"""

import sys
import os
import logging
from pathlib import Path
from typing import List, Dict, Any
import requests
import rasterio
from rasterio.merge import merge
from rasterio.windows import from_bounds
import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("fetch_dem")

import time

# Ensure proxy does not interfere with GDAL/requests direct calls
for _k in ["http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY"]:
    os.environ.pop(_k, None)

http_client = requests.Session()
http_client.trust_env = False

PC_STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1/search"
PC_SAS_URL = "https://planetarycomputer.microsoft.com/api/sas/v1/sign"


def get_sas_token(collection: str = "cop-dem-glo-30") -> str:
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


def query_dem_stac(bbox: List[float]) -> List[Dict[str, Any]]:
    """Query Planetary Computer for Copernicus DEM GLO-30 tiles."""
    body = {
        "collections": ["cop-dem-glo-30"],
        "bbox": bbox,
        "limit": 10
    }
    headers = {"Content-Type": "application/json"}
    pc_key = os.environ.get("PC_SDK_SUBSCRIPTION_KEY")
    if pc_key:
        headers["Ocp-Apim-Subscription-Key"] = pc_key

    try:
        resp = http_client.post(PC_STAC_URL, json=body, headers=headers, timeout=20)
    except requests.exceptions.RequestException as e:
        logger.error(f"Network error querying Copernicus DEM STAC: {e}")
        raise RuntimeError(f"Network error querying Copernicus DEM STAC: {e}")

    if resp.status_code == 403:
        logger.error("HTTP 403 Forbidden: Sandbox or network environment blocked access to Copernicus DEM STAC.")
        raise RuntimeError("HTTP 403 Forbidden when accessing Copernicus DEM STAC API.")

    if resp.status_code != 200:
        logger.error(f"DEM STAC search returned HTTP {resp.status_code}: {resp.text}")
        raise RuntimeError(f"DEM STAC search returned HTTP {resp.status_code}: {resp.text}")

    features = resp.json().get("features", [])
    return features


def get_aws_dem_tile_url(lat: int, lon: int) -> str:
    """Construct open AWS S3 HTTPS URL for Copernicus GLO-30 tile."""
    ns = "N" if lat >= 0 else "S"
    ew = "E" if lon >= 0 else "W"
    tile_name = f"Copernicus_DSM_COG_10_{ns}{abs(lat):02d}_00_{ew}{abs(lon):03d}_00_DEM"
    return f"https://copernicus-dem-30m.s3.amazonaws.com/{tile_name}/{tile_name}.tif"


def fetch_dem(bbox: List[float], out_dir: str, buffer_km: float = 10.0, force: bool = False) -> Path:
    """Fetch Copernicus DEM-30 tiles covering bbox (with optional buffer), merge/clip, and save as dem.tif and dem_buffered.tif."""
    from rasterio.warp import transform_bounds

    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    dem_tif = out_path / "dem.tif"
    dem_buf_tif = out_path / "dem_buffered.tif"

    target_tif = dem_buf_tif if buffer_km > 0 else dem_tif

    if not force and target_tif.exists():
        try:
            with rasterio.open(target_tif) as src:
                if src.count >= 1:
                    logger.info(f"Verified existing Copernicus DEM in {target_tif} ({src.width}x{src.height})")
                    return target_tif
        except Exception:
            logger.warning("Existing DEM corrupted; refetching...")

    min_lon, min_lat, max_lon, max_lat = bbox
    if buffer_km > 0:
        center_lat = (min_lat + max_lat) / 2.0
        dlat = buffer_km / 111.0
        dlon = buffer_km / (111.0 * np.cos(np.radians(center_lat)))
        clip_bbox = [min_lon - dlon, min_lat - dlat, max_lon + dlon, max_lat + dlat]
        logger.info(f"Fetching Copernicus DEM-30 with {buffer_km}km buffer: bbox={clip_bbox}...")
    else:
        clip_bbox = bbox
        logger.info(f"Fetching Copernicus DEM-30 for bbox: {bbox}...")

    c_min_lon, c_min_lat, c_max_lon, c_max_lat = clip_bbox

    # Determine tiles covering clip_bbox (1x1 degree grid)
    lat_min_int = int(np.floor(c_min_lat))
    lat_max_int = int(np.floor(c_max_lat))
    lon_min_int = int(np.floor(c_min_lon))
    lon_max_int = int(np.floor(c_max_lon))

    tile_urls = []
    token = get_sas_token("cop-dem-glo-30")
    if token:
        try:
            features = query_dem_stac(clip_bbox)
            for f in features:
                asset = f.get("assets", {}).get("data")
                if asset:
                    tile_urls.append(sign_url(asset["href"], token))
        except Exception as e:
            logger.warning(f"PC STAC query failed: {e}; using direct AWS Open Data Copernicus DEM")

    from .gdal_env import get_shared_gdal_env, log_worker_gdal_env, clear_vsi_cache
    for fetch_attempt in range(5):
        opened_datasets = []
        try:
            with get_shared_gdal_env(tag="DEM", AWS_NO_SIGN_REQUEST='YES'):
                log_worker_gdal_env("DEM", f"fetch_attempt={fetch_attempt+1}")
                for lat in range(lat_min_int, lat_max_int + 1):
                    for lon in range(lon_min_int, lon_max_int + 1):
                        aws_url = get_aws_dem_tile_url(lat, lon)
                        tile_src = None
                        # Use AWS Open Data Copernicus DEM directly
                        try:
                            logger.info(f"Opening DEM raster from AWS Open Data: {aws_url}...")
                            tile_src = rasterio.open(aws_url)
                        except Exception as e:
                            logger.warning(f"Failed opening AWS DEM ({e}); trying PC URL if available...")
                            if tile_urls:
                                for u in tile_urls:
                                    try:
                                        tile_src = rasterio.open(u)
                                        break
                                    except Exception:
                                        pass
                        if tile_src is None:
                            raise RuntimeError(f"Could not open DEM tile for lat={lat}, lon={lon}")
                        opened_datasets.append(tile_src)

                if len(opened_datasets) == 1:
                    src = opened_datasets[0]
                    if src.crs and src.crs.to_string() != "EPSG:4326":
                        proj_bounds = transform_bounds("EPSG:4326", src.crs, min_lon, min_lat, max_lon, max_lat)
                    else:
                        proj_bounds = (c_min_lon, c_min_lat, c_max_lon, c_max_lat)

                    window = from_bounds(*proj_bounds, transform=src.transform)
                    data = src.read(1, window=window)
                    out_transform = rasterio.windows.transform(window, src.transform)
                    out_meta = src.meta.copy()
                    out_meta.update({
                        "driver": "GTiff",
                        "height": data.shape[0],
                        "width": data.shape[1],
                        "transform": out_transform,
                        "count": 1,
                        "dtype": data.dtype
                    })
                    with rasterio.open(target_tif, "w", **out_meta) as dst:
                        dst.write(data, 1)
                        dst.set_band_description(1, "Elevation (m)")
                else:
                    mosaic, out_trans = merge(opened_datasets, bounds=(c_min_lon, c_min_lat, c_max_lon, c_max_lat))
                    out_meta = opened_datasets[0].meta.copy()
                    out_meta.update({
                        "driver": "GTiff",
                        "height": mosaic.shape[1],
                        "width": mosaic.shape[2],
                        "transform": out_trans,
                        "count": 1,
                        "dtype": mosaic.dtype
                    })
                    with rasterio.open(target_tif, "w", **out_meta) as dst:
                        dst.write(mosaic[0], 1)
                        dst.set_band_description(1, "Elevation (m)")

            logger.info(f"Successfully saved Copernicus DEM-30 to {target_tif}")
            return target_tif
        except Exception as e:
            logger.warning(f"Attempt {fetch_attempt + 1}/5 fetching Copernicus DEM failed: {e}")
            if fetch_attempt == 4:
                logger.error(f"Error fetching/clipping Copernicus DEM after 5 attempts: {e}")
                raise RuntimeError(f"Could not download and clip Copernicus DEM: {e}")
            clear_vsi_cache()
            time.sleep(2 * (fetch_attempt + 1))
        finally:
            for ds in opened_datasets:
                try:
                    ds.close()
                except Exception:
                    pass
            clear_vsi_cache()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Fetch Copernicus DEM-30")
    parser.add_argument("--bbox", type=float, nargs=4, required=True, help="min_lon min_lat max_lon max_lat")
    parser.add_argument("--out-dir", type=str, required=True, help="Output directory")
    args = parser.parse_args()

    fetch_dem(args.bbox, args.out_dir)
