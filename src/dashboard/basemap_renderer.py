"""
Offline Basemap Renderer for Disaster Assessment Dashboard.
Generates and caches read-only dark topographic hillshade PNGs from the run's Copernicus DEM-30 GeoTIFF,
and serves raw OSM waterways, roads, and place labels for offline client-side rendering.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

import numpy as np
import rasterio
from matplotlib.colors import LightSource
from PIL import Image

logger = logging.getLogger("basemap_renderer")


def generate_run_hillshade(run_folder: Path) -> Tuple[Optional[Path], Optional[Dict[str, Any]]]:
    """
    Renders dark-canvas topographic relief hillshade from Copernicus DEM-30.
    Caches output as processed/basemap_hillshade.png and processed/basemap_meta.json.
    """
    proc_dir = run_folder / "processed"
    proc_dir.mkdir(parents=True, exist_ok=True)
    out_png = proc_dir / "basemap_hillshade.png"
    out_meta = proc_dir / "basemap_meta.json"

    if out_png.exists() and out_meta.exists():
        try:
            meta = json.loads(out_meta.read_text(encoding="utf-8"))
            return out_png, meta
        except Exception:
            pass

    dem_candidates = [
        run_folder / "raw" / "dem" / "dem_buffered.tif",
        run_folder / "raw" / "dem" / "dem.tif",
        run_folder / "raw" / "dem" / "dem_glo30_buffered.tif",
    ]
    dem_path = next((p for p in dem_candidates if p.exists()), None)

    if not dem_path:
        logger.warning(f"No Copernicus DEM found in {run_folder / 'raw' / 'dem'}")
        return None, None

    try:
        with rasterio.open(dem_path) as src:
            dem = src.read(1)
            nodata = src.nodata
            bounds = src.bounds
            crs = src.crs

        valid = dem != nodata if nodata is not None else np.isfinite(dem)
        if not np.any(valid):
            return None, None

        min_val = float(np.nanmin(dem[valid]))
        dem_filled = np.where(valid, dem, min_val)

        # Light source from NW (315° az, 45° alt)
        ls = LightSource(azdeg=315, altdeg=45)
        res_m = 30.0
        shade = ls.hillshade(dem_filled, dx=res_m, dy=res_m)

        # Map to light official map product relief aesthetic
        # Neutral light background #F6F7F5 (RGB 246, 247, 245) with soft natural shading down to (RGB 200, 204, 202)
        r = (shade * 46 + 200).astype(np.uint8)
        g = (shade * 43 + 204).astype(np.uint8)
        b = (shade * 43 + 202).astype(np.uint8)
        a = np.where(valid, 255, 0).astype(np.uint8)

        rgba = np.stack([r, g, b, a], axis=-1)
        im = Image.fromarray(rgba, "RGBA")
        im.save(out_png, "PNG", optimize=True)

        # Bounds: [south, west], [north, east] in WGS84
        # If CRS is EPSG:4326
        if crs and crs.to_epsg() == 4326:
            w, s, e, n = bounds.left, bounds.bottom, bounds.right, bounds.top
        else:
            from rasterio.warp import transform_bounds
            w, s, e, n = transform_bounds(crs or "EPSG:32645", "EPSG:4326", bounds.left, bounds.bottom, bounds.right, bounds.top)

        meta = {
            "bounds": [[s, w], [n, e]],
            "bbox": [w, s, e, n],
            "width": int(im.width),
            "height": int(im.height),
            "dem_source": dem_path.name
        }
        out_meta.write_text(json.dumps(meta, indent=2), encoding="utf-8")
        logger.info(f"Generated cached hillshade basemap for {run_folder.name} ({im.width}x{im.height})")
        return out_png, meta

    except Exception as e:
        logger.error(f"Failed to generate hillshade for {run_folder.name}: {e}")
        return None, None
