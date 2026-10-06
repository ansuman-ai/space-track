"""
Shared rasterio.Env configuration for Layer 0 remote data ingestion.
Optimized to minimize HTTP roundtrips, reuse connections, and minimize latency over cloud object stores.
"""

from typing import Dict, Any
import rasterio

SHARED_GDAL_CONFIG: Dict[str, str] = {
    "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
    "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif,.TIF,.tiff,.jp2",
    "CPL_VSIL_CURL_USE_HEAD": "NO",
    "GDAL_HTTP_MERGE_CONSECUTIVE_RANGES": "YES",
    "GDAL_HTTP_MULTIPLEX": "YES",
    "GDAL_HTTP_VERSION": "2",
    "VSI_CACHE": "TRUE",
    "VSI_CACHE_SIZE": "100000000",
    "CPL_VSIL_CURL_CHUNK_SIZE": "2097152",      # 2 MB chunk cache
    "GDAL_INGESTED_BYTES_AT_OPEN": "131072",   # 128 KB initial header read
    "CURL_CA_BUNDLE": "/etc/ssl/certs/ca-certificates.crt",
    "GDAL_HTTP_CONNECTTIMEOUT": "15",
    "GDAL_HTTP_TIMEOUT": "30",
    "GDAL_HTTP_MAX_RETRY": "3"
}


def get_shared_gdal_env(**overrides) -> rasterio.Env:
    """Return a configured rasterio.Env context with shared latency-optimized settings."""
    cfg = dict(SHARED_GDAL_CONFIG)
    cfg.update(overrides)
    return rasterio.Env(**cfg)
