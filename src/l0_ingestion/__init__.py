"""
Layer 0: Raw Ingestion Module
Handles dynamic querying and downloading of:
- Sentinel-1 RTC pre/post pairs (same-orbit, relative orbit matched)
- Copernicus DEM GLO-30 elevation data
- Pre-event OpenStreetMap snapshots via ohsome API
"""

from .fetch_s1 import fetch_pair
from .fetch_dem import fetch_dem
from .fetch_osm import fetch_osm
from .fetch_s2 import fetch_s2

__all__ = ["fetch_pair", "fetch_dem", "fetch_osm", "fetch_s2"]
