"""
Geospatial visualization and raster-vector alignment utilities.
Provides unified functions to:
1. Accurately draw raster backgrounds with extent = (left, right, bottom, top) derived from transform metadata.
2. Reproject vector layers safely to the raster target CRS.
3. Draw pre-event OSM river centreline for built-in visual alignment verification.
"""

import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union, List
import numpy as np
import rasterio
import rasterio.windows
import rasterio.transform
import geopandas as gpd
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from shapely.geometry import LineString, MultiLineString
from shapely.ops import linemerge, unary_union


def reproject_vector(
    gdf_or_geom: Any,
    target_crs: Any = None
) -> Any:
    """
    Safely reprojects a GeoDataFrame or geometry to target_crs.
    """
    if gdf_or_geom is None or target_crs is None:
        return gdf_or_geom
    if isinstance(gdf_or_geom, gpd.GeoDataFrame):
        if len(gdf_or_geom) == 0:
            return gdf_or_geom.copy()
        if gdf_or_geom.crs is None:
            return gdf_or_geom.set_crs(target_crs)
        if gdf_or_geom.crs != target_crs:
            return gdf_or_geom.to_crs(target_crs)
        return gdf_or_geom
    if hasattr(gdf_or_geom, "to_crs"):
        return gdf_or_geom.to_crs(target_crs)
    return gdf_or_geom


DEFAULT_RIVER_PATH = "data/raw/osm/osm_river_centerline.geojson"


def ensure_river_centerline_exists(
    river_geojson_path: str = DEFAULT_RIVER_PATH,
    stream_mask_path: str = "data/interim/stream_mask.tif",
    osm_waterways_path: str = "data/raw/osm/osm_waterways.geojson",
    target_crs: Optional[str] = None
) -> Path:
    """
    Ensures that a pre-event river centreline GeoDataFrame exists on disk.
    If not already generated, extracts it from stream_mask.tif drainage network.
    """
    out_path = Path(river_geojson_path)
    if out_path.exists():
        return out_path

    out_path.parent.mkdir(parents=True, exist_ok=True)
    st_path = Path(stream_mask_path)
    if not st_path.exists():
        # Fallback if stream mask not available
        return out_path

    with rasterio.open(st_path) as src:
        st = src.read(1)
        trans = src.transform
        crs = src.crs or target_crs

    h, w = st.shape
    rows, cols = np.where(st == 1)
    lines = []
    for r, c in zip(rows, cols):
        x1, y1 = trans * (c + 0.5, r + 0.5)
        for dr, dc in [(0, 1), (1, 0), (1, 1), (1, -1)]:
            nr, nc = r + dr, c + dc
            if 0 <= nr < h and 0 <= nc < w and st[nr, nc] == 1:
                x2, y2 = trans * (nc + 0.5, nr + 0.5)
                lines.append(LineString([(x1, y1), (x2, y2)]))

    if lines:
        merged = linemerge(unary_union(lines))
        gdf = gpd.GeoDataFrame([{"name": "OSM River Centreline", "geometry": merged}], crs=crs)
        gdf.to_file(out_path, driver="GeoJSON")
    return out_path


DEFAULT_WATERWAYS_PATH = "data/raw/osm/osm_waterways.geojson"


def draw_osm_river_centreline(
    ax: plt.Axes,
    target_crs: Any = None,
    river_path: str = DEFAULT_WATERWAYS_PATH,
    color: str = "#00e5ff",
    lw: float = 1.2,
    linestyle: str = "-",
    alpha: float = 0.85,
    zorder: int = 15,
    label: str = "OSM waterway=river (Alignment Check)",
    clip_bounds: Optional[Tuple[float, float, float, float]] = None
) -> Optional[Line2D]:
    """
    Draws ONLY OSM waterway=river features (and riverbank/water polygon outlines if present).
    The main river line/channel is MISSING from OSM data (only bounding boxes present).
    """
    p = Path(river_path)
    if not p.exists():
        return None

    try:
        w_gdf = gpd.read_file(p)
        # Strictly filter ONLY waterway=river (and riverbank / natural=water if present)
        mask = (w_gdf.get("waterway") == "river")
        if "natural" in w_gdf.columns:
            mask = mask | (w_gdf["natural"] == "water")
        if "waterway" in w_gdf.columns and "riverbank" in w_gdf["waterway"].values:
            mask = mask | (w_gdf["waterway"] == "riverbank")

        rivers_gdf = w_gdf[mask].copy()
        if len(rivers_gdf) == 0:
            return None

        rivers_gdf = reproject_vector(rivers_gdf, target_crs)

        if clip_bounds is not None:
            xmin, ymin, xmax, ymax = clip_bounds
            clipped = rivers_gdf.clip_by_rect(xmin, ymin, xmax, ymax)
            clipped = clipped[~clipped.is_empty]
            if len(clipped) == 0:
                return None
            lines = clipped.apply(lambda g: g.boundary if g.geom_type in ["Polygon", "MultiPolygon"] else g)
        else:
            lines = rivers_gdf.geometry.apply(lambda g: g.boundary if g.geom_type in ["Polygon", "MultiPolygon"] else g)

        lines.plot(
            ax=ax,
            color=color,
            linewidth=lw,
            linestyle=linestyle,
            alpha=alpha,
            zorder=zorder
        )
        return Line2D([0], [0], color=color, lw=lw, linestyle=linestyle, label=label)
    except Exception as e:
        print(f"Warning: could not draw OSM waterway=river: {e}")
        return None


def plot_raster_background(
    ax: plt.Axes,
    raster_source: Any,
    transform: Any = None,
    bounds: Optional[Tuple[float, float, float, float]] = None,
    clip_extent: Optional[Tuple[float, float, float, float]] = None,
    cmap: Optional[str] = None,
    vmin: Optional[float] = None,
    vmax: Optional[float] = None,
    origin: str = "upper",
    zorder: int = 1,
    alpha: float = 1.0
) -> Tuple[Tuple[float, float, float, float], Any]:
    """
    Draws raster background strictly using georeferenced extents derived from raster bounds.
    
    Parameters:
    - ax: Matplotlib axes to draw on.
    - raster_source: Filepath (.tif or .npz) OR 2D/3D numpy array.
    - transform: Affine transform (required if raster_source is an array).
    - bounds: (left, bottom, right, top) if available.
    - clip_extent: (xmin, xmax, ymin, ymax) target spatial crop window.
    
    Returns:
    - extent: (left, right, bottom, top) passed to imshow.
    - im: AxesImage object returned by imshow.
    """
    if isinstance(raster_source, (str, Path)):
        p = Path(raster_source)
        if p.suffix == ".npz":
            data = np.load(p)
            if "visual" in data:
                arr = data["visual"]
            elif "vis" in data:
                arr = data["vis"]
            else:
                arr = data[list(data.keys())[0]]
            if transform is None:
                # Read transform from reference hazard_classes.tif if available
                ref_tif = Path("data/processed/hazard_classes.tif")
                if ref_tif.exists():
                    with rasterio.open(ref_tif) as src:
                        transform = src.transform
        else:
            with rasterio.open(p) as src:
                arr = src.read()
                if arr.shape[0] == 1:
                    arr = arr[0]
                transform = src.transform
                bounds = (src.bounds.left, src.bounds.bottom, src.bounds.right, src.bounds.top)
    else:
        arr = np.asarray(raster_source)

    if transform is None:
        raise ValueError("Affine transform matrix must be provided to accurately plot raster background.")

    h = arr.shape[-2]
    w = arr.shape[-1]

    if clip_extent is not None:
        xmin, xmax, ymin, ymax = clip_extent
        inv_trans = ~transform
        c1, r_top = inv_trans * (xmin, ymax)
        c2, r_bot = inv_trans * (xmax, ymin)

        r1_idx = int(round(min(r_top, r_bot)))
        r2_idx = int(round(max(r_top, r_bot)))
        c1_idx = int(round(min(c1, c2)))
        c2_idx = int(round(max(c1, c2)))

        r1_cl = max(0, min(r1_idx, h))
        r2_cl = max(0, min(r2_idx, h))
        c1_cl = max(0, min(c1_idx, w))
        c2_cl = max(0, min(c2_idx, w))

        if r2_cl <= r1_cl or c2_cl <= c1_cl:
            extent = (clip_extent[0], clip_extent[1], clip_extent[2], clip_extent[3])
            ax.set_facecolor("#151515")
            ax.set_xlim(clip_extent[0], clip_extent[1])
            ax.set_ylim(clip_extent[2], clip_extent[3])
            return extent, None

        win = rasterio.windows.Window(c1_cl, r1_cl, c2_cl - c1_cl, r2_cl - r1_cl)
        left, bottom, right, top = rasterio.windows.bounds(win, transform)
        extent = (left, right, bottom, top)

        if arr.ndim == 3:
            if arr.shape[0] in [3, 4]:
                sub_arr = arr[:, r1_cl:r2_cl, c1_cl:c2_cl].transpose(1, 2, 0)
            else:
                sub_arr = arr[r1_cl:r2_cl, c1_cl:c2_cl]
        else:
            sub_arr = arr[r1_cl:r2_cl, c1_cl:c2_cl]
    else:
        if bounds is not None:
            extent = (bounds[0], bounds[2], bounds[1], bounds[3])
        else:
            b = rasterio.transform.array_bounds(h, w, transform)
            extent = (b[0], b[2], b[1], b[3])

        if arr.ndim == 3 and arr.shape[0] in [3, 4]:
            sub_arr = arr.transpose(1, 2, 0)
        else:
            sub_arr = arr

    if sub_arr.size == 0:
        ax.set_facecolor("#151515")
        return extent, None

    if sub_arr.ndim == 3:
        im = ax.imshow(sub_arr, extent=extent, origin=origin, zorder=zorder, alpha=alpha)
    else:
        im = ax.imshow(sub_arr, extent=extent, origin=origin, zorder=zorder, alpha=alpha, cmap=cmap, vmin=vmin, vmax=vmax)

    ax.set_xlim(extent[0], extent[1])
    ax.set_ylim(extent[2], extent[3])
    return extent, im
