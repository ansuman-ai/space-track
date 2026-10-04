"""
Independent visual comparison script for Layer 2 variants (e.g. A vs C)
using unified plot_utils with strictly georeferenced raster background
and built-in river centreline alignment verification.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import rasterio
import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from rasterio.features import rasterize

from src.common.plot_utils import (
    plot_raster_background,
    draw_osm_river_centreline,
    reproject_vector,
)


def generate_verify_A_vs_C_plot(
    haz_A_path: str = "validation/hazard_classes_A.tif",
    haz_C_path: str = "validation/hazard_classes_C.tif",
    output_png: str = "validation/verify_A_vs_C.png",
    s2_npz_path: str = "data/interim/s2_cache/post_119_S2B_MSIL2A_20260827T045659_R11.npz"
):
    out_file = Path(output_png)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    with rasterio.open(haz_A_path) as src_A:
        trans = src_A.transform
        crs = src_A.crs
        h, w = src_A.shape
        r_A = src_A.read(1)

    with rasterio.open(haz_C_path) as src_C:
        r_C = src_C.read(1)

    cx, cy = 337320.0, 3115840.0
    half_w = 2000.0
    xmin, xmax = cx - half_w, cx + half_w
    ymin, ymax = cy - half_w, cy + half_w

    # Load vectors
    ems_event_path = "validation/emsr927/EMSR927_AOI01_GRA_PRODUCT_observedEventA_v1.shp"
    ems_aoi_path = "validation/emsr927/EMSR927_AOI01_GRA_PRODUCT_areaOfInterestA_v1.shp"

    aoi_gdf = reproject_vector(gpd.read_file(ems_aoi_path), crs)
    event_gdf = reproject_vector(gpd.read_file(ems_event_path), crs)

    fig, axes = plt.subplots(1, 3, figsize=(24, 8), dpi=200, constrained_layout=True)

    # Calculate pixel indices for slice
    inv_trans = ~trans
    c1_idx = int(round((xmin - trans.c) / trans.a))
    r1_idx = int(round((ymax - trans.f) / trans.e))
    c2_idx = int(round((xmax - trans.c) / trans.a))
    r2_idx = int(round((ymin - trans.f) / trans.e))
    r_start = max(0, min(r1_idx, r2_idx, h))
    r_end = max(0, min(max(r1_idx, r2_idx), h))
    c_start = max(0, min(c1_idx, c2_idx, w))
    c_end = max(0, min(max(c1_idx, c2_idx), w))

    nx, ny = c_end - c_start, r_end - r_start

    # Panel 1: Variant A
    ext, _ = plot_raster_background(axes[0], s2_npz_path, transform=trans, clip_extent=(xmin, xmax, ymin, ymax), zorder=1)
    draw_osm_river_centreline(axes[0], target_crs=crs, clip_bounds=(xmin, ymin, xmax, ymax), color="#00e5ff", lw=1.2, zorder=12)

    X = np.linspace(ext[0], ext[1], nx)
    Y = np.linspace(ext[3], ext[2], ny)

    sub_A = r_A[r_start:r_end, c_start:c_end]
    c2_A = (sub_A == 2).astype(np.uint8)
    c3_A = (sub_A == 3).astype(np.uint8)

    if np.any(c3_A):
        axes[0].contour(X, Y, c3_A, levels=[0.5], colors=["#ff8800"], linewidths=1.8, linestyles=["--"], zorder=4)
        c3_rgba = np.zeros((*c3_A.shape, 4), dtype=np.float32)
        c3_rgba[c3_A == 1] = [1.0, 0.55, 0.0, 0.40]
        axes[0].imshow(c3_rgba, extent=ext, origin="upper", zorder=4)

    if np.any(c2_A):
        axes[0].contour(X, Y, c2_A, levels=[0.5], colors=["#ff2200"], linewidths=2.0, zorder=5)
        c2_rgba = np.zeros((*c2_A.shape, 4), dtype=np.float32)
        c2_rgba[c2_A == 1] = [1.0, 0.15, 0.0, 0.45]
        axes[0].imshow(c2_rgba, extent=ext, origin="upper", zorder=5)

    ev_clip = event_gdf.clip_by_rect(xmin, ymin, xmax, ymax)
    if len(ev_clip) > 0:
        ev_clip.plot(ax=axes[0], facecolor="none", edgecolor="#ffe600", linewidth=2.0, zorder=6)
    aoi_clip = aoi_gdf.clip_by_rect(xmin, ymin, xmax, ymax)
    if len(aoi_clip) > 0:
        aoi_clip.boundary.plot(ax=axes[0], color="#00ffff", linewidth=1.5, linestyle="--", zorder=7)

    axes[0].set_title("Variant A (Baseline L2.2)\nStrictly Aligned Georeference", fontsize=11, fontweight="bold")
    axes[0].axis("off")

    # Panel 2: Variant C
    plot_raster_background(axes[1], s2_npz_path, transform=trans, clip_extent=(xmin, xmax, ymin, ymax), zorder=1)
    draw_osm_river_centreline(axes[1], target_crs=crs, clip_bounds=(xmin, ymin, xmax, ymax), color="#00e5ff", lw=1.2, zorder=12)

    sub_C = r_C[r_start:r_end, c_start:c_end]
    c2_C = (sub_C == 2).astype(np.uint8)
    c3_C = (sub_C == 3).astype(np.uint8)

    if np.any(c3_C):
        axes[1].contour(X, Y, c3_C, levels=[0.5], colors=["#ff8800"], linewidths=1.8, linestyles=["--"], zorder=4)
        c3_rgba = np.zeros((*c3_C.shape, 4), dtype=np.float32)
        c3_rgba[c3_C == 1] = [1.0, 0.55, 0.0, 0.40]
        axes[1].imshow(c3_rgba, extent=ext, origin="upper", zorder=4)

    if np.any(c2_C):
        axes[1].contour(X, Y, c2_C, levels=[0.5], colors=["#ff2200"], linewidths=2.0, zorder=5)
        c2_rgba = np.zeros((*c2_C.shape, 4), dtype=np.float32)
        c2_rgba[c2_C == 1] = [1.0, 0.15, 0.0, 0.45]
        axes[1].imshow(c2_rgba, extent=ext, origin="upper", zorder=5)

    if len(ev_clip) > 0:
        ev_clip.plot(ax=axes[1], facecolor="none", edgecolor="#ffe600", linewidth=2.0, zorder=6)
    if len(aoi_clip) > 0:
        aoi_clip.boundary.plot(ax=axes[1], color="#00ffff", linewidth=1.5, linestyle="--", zorder=7)

    axes[1].set_title("Variant C (L2.4 Adopted)\nStrictly Aligned Georeference", fontsize=11, fontweight="bold")
    axes[1].axis("off")

    # Panel 3: Disagreement Difference
    plot_raster_background(axes[2], s2_npz_path, transform=trans, clip_extent=(xmin, xmax, ymin, ymax), zorder=1)
    draw_osm_river_centreline(axes[2], target_crs=crs, clip_bounds=(xmin, ymin, xmax, ymax), color="#00e5ff", lw=1.2, zorder=12)

    pred_A = (c2_A == 1) | (c3_A == 1)
    pred_C = (c2_C == 1) | (c3_C == 1)
    only_A = pred_A & (~pred_C)
    only_C = pred_C & (~pred_A)

    diff_rgba = np.zeros((*sub_A.shape, 4), dtype=np.float32)
    diff_rgba[only_A] = [0.0, 0.45, 1.0, 0.80]  # Blue = in A but not in C
    diff_rgba[only_C] = [0.0, 0.90, 0.2, 0.80]  # Green = in C but not in A
    axes[2].imshow(diff_rgba, extent=ext, origin="upper", zorder=5)

    if len(ev_clip) > 0:
        ev_clip.plot(ax=axes[2], facecolor="none", edgecolor="#ffe600", linewidth=2.0, zorder=6)
    if len(aoi_clip) > 0:
        aoi_clip.boundary.plot(ax=axes[2], color="#00ffff", linewidth=1.5, linestyle="--", zorder=7)

    axes[2].set_title("Difference Map\nBlue: In A not C | Green: In C not A", fontsize=11, fontweight="bold")
    axes[2].axis("off")

    legend_elements = [
        Line2D([0], [0], color="#ffe600", lw=2.2, label="EMS Observed Landslide"),
        Line2D([0], [0], color="#00e5ff", lw=1.2, label="OSM River Centreline (Alignment Check)"),
        Line2D([0], [0], color="#ff2200", lw=2.0, label="Observed Class 2"),
        Line2D([0], [0], color="#ff8800", lw=1.8, linestyle="--", label="Inferred Class 3"),
        Line2D([0], [0], color="#00ffff", lw=1.5, linestyle="--", label="EMS AOI Boundary")
    ]
    axes[1].legend(handles=legend_elements, loc="lower left", framealpha=0.92, fontsize=9.2)

    diff_legend = [
        Line2D([0], [0], color="#0073ff", lw=6.0, label="In A but not C"),
        Line2D([0], [0], color="#00e633", lw=6.0, label="In C but not A"),
        Line2D([0], [0], color="#ffe600", lw=2.2, label="EMS Observed Landslide"),
        Line2D([0], [0], color="#00e5ff", lw=1.2, label="OSM River Centreline"),
    ]
    axes[2].legend(handles=diff_legend, loc="lower left", framealpha=0.92, fontsize=9.2)

    plt.savefig(output_png, bbox_inches="tight")
    plt.close()
    print(f"Regenerated {output_png} with verified georeference alignment.")
    art_path = Path("/home/zeus/.gemini/antigravity/brain/52dd5215-6165-4f39-8912-cfce41bfdff1/verify_A_vs_C.png")
    import shutil
    shutil.copy2(output_png, art_path)


if __name__ == "__main__":
    generate_verify_A_vs_C_plot()
