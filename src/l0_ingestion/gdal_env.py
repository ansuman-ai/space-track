"""
Shared rasterio.Env configuration for Layer 0 remote data ingestion.
Optimized to minimize HTTP roundtrips, reuse connections, and minimize latency over cloud object stores.
"""

from typing import Dict, Any
import rasterio

import logging

logger = logging.getLogger("gdal_env")

SHARED_GDAL_CONFIG: Dict[str, str] = {
    "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
    "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif,.TIF,.tiff,.jp2",
    "CPL_VSIL_CURL_USE_HEAD": "NO",
    "GDAL_HTTP_MERGE_CONSECUTIVE_RANGES": "NO",
    "GDAL_HTTP_MULTIPLEX": "NO",
    "GDAL_HTTP_VERSION": "1.1",
    "GDAL_HTTP_MULTIRANGE": "SERIAL",
    "VSI_CACHE": "TRUE",
    "VSI_CACHE_SIZE": "100000000",
    "CPL_VSIL_CURL_CHUNK_SIZE": "2097152",      # 2 MB chunk cache
    "GDAL_INGESTED_BYTES_AT_OPEN": "131072",   # 128 KB initial header read
    "CURL_CA_BUNDLE": "/etc/ssl/certs/ca-certificates.crt",
    "GDAL_HTTP_CONNECTTIMEOUT": "30",
    "GDAL_HTTP_TIMEOUT": "60",
    "GDAL_HTTP_MAX_RETRY": "5",
    "GDAL_HTTP_RETRY_DELAY": "2",
    "GDAL_HTTP_RETRY_CODES": "429,500,502,503,504,0"
}


def log_effective_gdal_config(tag: str, cfg: Dict[str, Any]) -> None:
    """Print the effective GDAL configuration at the start of remote fetches."""
    cfg_summary = ", ".join(f"{k}={v}" for k, v in sorted(cfg.items()) if k.startswith("GDAL_") or k.startswith("CPL_") or "HTTP" in k or "CACHE" in k)
    logger.info(f"[GDAL_CONFIG] Effective settings for {tag}: {cfg_summary}")


def log_worker_gdal_env(sensor_tag: str, detail: str = "") -> Dict[str, str]:
    """
    Log and verify active GDAL options inside worker threads/processes at the moment of raster reads.
    Proves that thread-local rasterio.Env settings are in effect.
    """
    import threading
    from rasterio._env import get_gdal_config
    keys = [
        "GDAL_DISABLE_READDIR_ON_OPEN",
        "CPL_VSIL_CURL_CHUNK_SIZE",
        "GDAL_HTTP_TIMEOUT",
        "GDAL_HTTP_VERSION",
        "GDAL_HTTP_MAX_RETRY",
        "GDAL_HTTP_MULTIRANGE",
        "VSI_CACHE"
    ]
    effective = {k: get_gdal_config(k) for k in keys}
    eff_str = ", ".join(f"{k}={v}" for k, v in effective.items())
    logger.info(f"[GDAL_WORKER_VERIFY] [{sensor_tag}] thread={threading.current_thread().name} {detail} -> {eff_str}")
    return effective


def get_shared_gdal_env(tag: str = "remote_fetch", **overrides) -> rasterio.Env:
    """Return a configured rasterio.Env context with shared latency-optimized settings."""
    cfg = dict(SHARED_GDAL_CONFIG)
    cfg.update(overrides)
    log_effective_gdal_config(tag, cfg)
    return rasterio.Env(**cfg)


