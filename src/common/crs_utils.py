"""
Common Coordinate Reference System (CRS) and UTM utilities.
"""

from typing import List, Union


def auto_utm_crs(bbox: List[float]) -> str:
    """Computes UTM EPSG CRS string from WGS84 bbox [min_lon, min_lat, max_lon, max_lat].
    
    Correctly computes zone number (1-60) from longitude center and selects
    EPSG:326xx for Northern hemisphere (lat >= 0) or EPSG:327xx for Southern hemisphere (lat < 0).
    """
    center_lon = (float(bbox[0]) + float(bbox[2])) / 2.0
    center_lat = (float(bbox[1]) + float(bbox[3])) / 2.0
    zone = int((center_lon + 180) // 6) + 1
    zone = max(1, min(60, zone))
    if center_lat >= 0:
        return f"EPSG:{32600 + zone}"
    else:
        return f"EPSG:{32700 + zone}"


# Alias for backward compatibility
compute_utm_crs = auto_utm_crs
