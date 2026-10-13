"""
Offline Basemap & DEM Hillshade Tile Renderer for Disaster Assessment Dashboard.
Generates and caches:
1. Full-extent topographic relief hillshade PNG for offline fallback.
2. Web Mercator XYZ hillshade tiles (z=9-15) for crisp, multi-zoom terrain overlay.
3. Serves raw OSM waterways, roads, and place labels for offline client-side rendering.
"""

import json
import logging
import math
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

import numpy as np
import rasterio
from rasterio.transform import array_bounds
from rasterio.warp import calculate_default_transform, reproject, Resampling
from matplotlib.colors import LightSource
from PIL import Image

logger = logging.getLogger("basemap_renderer")


def tile_bounds_3857(x: int, y: int, z: int) -> Tuple[float, float, float, float]:
    """Returns (minx, miny, maxx, maxy) in EPSG:3857 meters for tile (x, y, z)."""
    origin_shift = 20037508.342789244
    initial_resolution = 2 * origin_shift / 256.0
    res = initial_resolution / (2 ** z)
    minx = x * 256 * res - origin_shift
    maxx = (x + 1) * 256 * res - origin_shift
    maxy = origin_shift - y * 256 * res
    miny = origin_shift - (y + 1) * 256 * res
    return minx, miny, maxx, maxy


def deg2num(lat_deg: float, lon_deg: float, zoom: int) -> Tuple[int, int]:
    """Converts WGS84 lat/lon to Web Mercator tile x, y."""
    lat_rad = math.radians(lat_deg)
    n = 1 << zoom
    xtile = int((lon_deg + 180.0) / 360.0 * n)
    ytile = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return xtile, ytile


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

        # Map to light official map product relief aesthetic for offline fallback PNG
        r = (shade * 46 + 200).astype(np.uint8)
        g = (shade * 43 + 204).astype(np.uint8)
        b = (shade * 43 + 202).astype(np.uint8)
        a = np.where(valid, 255, 0).astype(np.uint8)

        rgba = np.stack([r, g, b, a], axis=-1)
        im = Image.fromarray(rgba, "RGBA")
        im.save(out_png, "PNG", optimize=True)

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


def generate_run_hillshade_tiles(run_folder: Path, min_zoom: int = 9, max_zoom: int = 14) -> Path:
    """
    Generates and caches Web Mercator XYZ tiles (z=9-14) from Copernicus DEM-30
    under processed/dem_tiles/{z}/{x}/{y}.png.
    Uses natural greyscale shading (0=shadow, 255=highlight, transparent outside DEM)
    for terrain overlay over OSM base tiles.
    """
    tiles_root = run_folder / "processed" / "dem_tiles"
    complete_flag = tiles_root / ".complete"

    if complete_flag.exists():
        return tiles_root

    dem_candidates = [
        run_folder / "raw" / "dem" / "dem_buffered.tif",
        run_folder / "raw" / "dem" / "dem.tif",
        run_folder / "raw" / "dem" / "dem_glo30_buffered.tif",
    ]
    dem_path = next((p for p in dem_candidates if p.exists()), None)
    if not dem_path:
        logger.warning(f"No Copernicus DEM found in {run_folder / 'raw' / 'dem'} for tiles")
        return tiles_root

    try:
        with rasterio.open(dem_path) as src:
            dem = src.read(1)
            nodata = src.nodata
            bounds = src.bounds
            crs = src.crs
            src_transform = src.transform

        valid = dem != nodata if nodata is not None else np.isfinite(dem)
        if not np.any(valid):
            return tiles_root

        min_val = float(np.nanmin(dem[valid]))
        dem_filled = np.where(valid, dem, min_val)

        ls = LightSource(azdeg=315, altdeg=45)
        shade = ls.hillshade(dem_filled, dx=30.0, dy=30.0)

        # Greyscale hillshade for mix-blend-mode: multiply:
        # Highlights/flat terrain map to near-white (245-255, transparent effect in multiply),
        # ridges and shadowed slopes shade down to ~120-135.
        gray = (shade * 125 + 130).astype(np.uint8)
        alpha = np.where(valid, 255, 0).astype(np.uint8)
        rgba = np.stack([gray, gray, gray, alpha], axis=-1)

        # Reproject to EPSG:3857 (Web Mercator)
        dst_crs = "EPSG:3857"
        dst_transform, dst_w, dst_h = calculate_default_transform(
            crs, dst_crs, rgba.shape[1], rgba.shape[0], *bounds
        )
        dst_rgba = np.zeros((4, dst_h, dst_w), dtype=np.uint8)
        for b in range(4):
            reproject(
                source=rgba[..., b],
                destination=dst_rgba[b],
                src_transform=src_transform,
                src_crs=crs,
                dst_transform=dst_transform,
                dst_crs=dst_crs,
                resampling=Resampling.bilinear
            )

        # Transform bounds in EPSG:3857
        x_min, y_min, x_max, y_max = array_bounds(dst_h, dst_w, dst_transform)
        dst_img = Image.fromarray(np.transpose(dst_rgba, (1, 2, 0)), "RGBA")

        # Convert DEM bounds to WGS84 for tile coordinate calculation
        if crs and crs.to_epsg() == 4326:
            w4326, s4326, e4326, n4326 = bounds.left, bounds.bottom, bounds.right, bounds.top
        else:
            from rasterio.warp import transform_bounds
            w4326, s4326, e4326, n4326 = transform_bounds(crs or "EPSG:32645", "EPSG:4326", bounds.left, bounds.bottom, bounds.right, bounds.top)

        tiles_root.mkdir(parents=True, exist_ok=True)
        tile_count = 0

        for z in range(min_zoom, max_zoom + 1):
            x0, y1 = deg2num(s4326, w4326, z)
            x1, y0 = deg2num(n4326, e4326, z)
            min_x, max_x = min(x0, x1), max(x0, x1)
            min_y, max_y = min(y0, y1), max(y0, y1)

            for x in range(min_x, max_x + 1):
                z_x_dir = tiles_root / str(z) / str(x)
                for y in range(min_y, max_y + 1):
                    t_minx, t_miny, t_maxx, t_maxy = tile_bounds_3857(x, y, z)
                    if t_maxx < x_min or t_minx > x_max or t_maxy < y_min or t_miny > y_max:
                        continue

                    px0 = int(round((t_minx - x_min) / (x_max - x_min) * dst_w))
                    px1 = int(round((t_maxx - x_min) / (x_max - x_min) * dst_w))
                    py0 = int(round((y_max - t_maxy) / (y_max - y_min) * dst_h))
                    py1 = int(round((y_max - t_miny) / (y_max - y_min) * dst_h))

                    if px1 <= px0 or py1 <= py0:
                        continue

                    tile_img = dst_img.crop((px0, py0, px1, py1)).resize((256, 256), Image.Resampling.BILINEAR)
                    # Check if tile has any visible pixels
                    tile_alpha = np.array(tile_img)[..., 3]
                    if not np.any(tile_alpha > 0):
                        continue

                    z_x_dir.mkdir(parents=True, exist_ok=True)
                    tile_img.save(z_x_dir / f"{y}.png", "PNG", optimize=True)
                    tile_count += 1

        complete_flag.write_text(json.dumps({"tile_count": tile_count, "min_zoom": min_zoom, "max_zoom": max_zoom}))
        logger.info(f"Generated {tile_count} hillshade XYZ tiles (z={min_zoom}..{max_zoom}) for {run_folder.name}")
        return tiles_root

    except Exception as e:
        logger.error(f"Failed to generate hillshade tiles for {run_folder.name}: {e}")
        return tiles_root
