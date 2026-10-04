"""
Layer 3 Validation: Copernicus EMS EMSR927 Evaluation.
Evaluates Layer 2 hazard detection outputs against Copernicus EMS EMSR927 (AOI01 Syabru Besi),
using unified plot_utils and built-in river centreline alignment check.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import geopandas as gpd
import rasterio
from rasterio.features import rasterize
from scipy.ndimage import distance_transform_edt
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

from src.common.plot_utils import (
    plot_raster_background,
    draw_osm_river_centreline,
    reproject_vector,
)


def run_validation():
    ems_dir = Path("validation/emsr927")
    output_png = Path("validation/quicklook_validation.png")

    # 1. Inspect package
    vector_files = sorted(list(ems_dir.glob("*.shp")))
    print(f"Found {len(vector_files)} shapefiles in {ems_dir}")

    # 2. Load Layer 2 prediction raster and spatial reference
    with rasterio.open("data/processed/hazard_classes.tif") as src:
        hazard_raster = src.read(1)
        trans = src.transform
        crs = src.crs
        h, w = hazard_raster.shape

    dx = abs(trans.a)
    pixel_area_m2 = dx * abs(trans.e)

    # Load S2 validity mask from interim cache
    from src.l2_detection.s2_composite import prepare_s2_event_and_control_composites
    s2_data = prepare_s2_event_and_control_composites("data/interim/s2_cache", 60.0, dx)
    s2_valid = s2_data["s2_event_valid"]

    # 3. Load EMS AOI and Landslide polygons
    aoi_gdf = gpd.read_file(ems_dir / "EMSR927_AOI01_GRA_PRODUCT_areaOfInterestA_v1.shp").to_crs(crs)
    aoi_mask = rasterize([(g, 1) for g in aoi_gdf.geometry], out_shape=(h, w), transform=trans, fill=0, dtype=np.uint8) == 1

    ems_gdf = gpd.read_file(ems_dir / "EMSR927_AOI01_GRA_PRODUCT_observedEventA_v1.shp").to_crs(crs)
    ems_mask = rasterize([(g, 1) for g in ems_gdf.geometry], out_shape=(h, w), transform=trans, fill=0, dtype=np.uint8) == 1

    # Cloud statistics in AOI
    total_aoi_px = np.sum(aoi_mask)
    valid_aoi_px = np.sum(aoi_mask & s2_valid)
    cloud_aoi_px = np.sum(aoi_mask & (~s2_valid))

    print(f"Total AOI Area: {total_aoi_px * pixel_area_m2 / 1e6:.3f} km² ({total_aoi_px} px)")
    print(f"Cloud/NoData in AOI: {cloud_aoi_px * pixel_area_m2 / 1e6:.3f} km² ({cloud_aoi_px / total_aoi_px * 100:.1f}%)")
    print(f"Valid Evaluated Area: {valid_aoi_px * pixel_area_m2 / 1e6:.3f} km² ({valid_aoi_px / total_aoi_px * 100:.1f}%)")

    # Evaluation masks
    eval_mask = aoi_mask & s2_valid
    pred_bool = (hazard_raster == 2) & eval_mask
    gt_bool = ems_mask & eval_mask

    # 4. Strict 10m metrics
    tp = np.sum(pred_bool & gt_bool)
    fp = np.sum(pred_bool & (~gt_bool))
    fn = np.sum((~pred_bool) & gt_bool)

    iou_10m = tp / (tp + fp + fn) if (tp + fp + fn) > 0 else 0
    prec_10m = tp / (tp + fp) if (tp + fp) > 0 else 0
    rec_10m = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1_10m = 2 * prec_10m * rec_10m / (prec_10m + rec_10m) if (prec_10m + rec_10m) > 0 else 0

    # 5. 20m tolerance metrics
    dist_to_gt = distance_transform_edt(~gt_bool) * dx
    dist_to_pred = distance_transform_edt(~pred_bool) * dx
    tp_tol_pred = np.sum(pred_bool & (dist_to_gt <= 20.0))
    tp_tol_gt = np.sum(gt_bool & (dist_to_pred <= 20.0))
    prec_20m = tp_tol_pred / np.sum(pred_bool) if np.sum(pred_bool) > 0 else 0
    rec_20m = tp_tol_gt / np.sum(gt_bool) if np.sum(gt_bool) > 0 else 0
    f1_20m = 2 * prec_20m * rec_20m / (prec_20m + rec_20m) if (prec_20m + rec_20m) > 0 else 0
    iou_20m = tp_tol_pred / (np.sum(pred_bool) + np.sum(gt_bool) - tp_tol_gt)

    ours_area_km2 = np.sum(pred_bool) * pixel_area_m2 / 1e6
    ems_eval_area_km2 = np.sum(gt_bool) * pixel_area_m2 / 1e6
    ems_total_area_km2 = np.sum(ems_mask & aoi_mask) * pixel_area_m2 / 1e6

    print("\n--- RESULTS ---")
    print(f"Ours Class 2 Area: {ours_area_km2:.4f} km²")
    print(f"EMS Landslide in valid AOI: {ems_eval_area_km2:.4f} km² (Total: {ems_total_area_km2:.4f} km²)")
    print(f"Strict 10m: IoU={iou_10m:.4f}, F1={f1_10m:.4f}, Prec={prec_10m:.4f}, Rec={rec_10m:.4f}")
    print(f"Tolerant 20m: IoU={iou_20m:.4f}, F1={f1_20m:.4f}, Prec={prec_20m:.4f}, Rec={rec_20m:.4f}")

    # 6. Syabru Besi Overlay Plot
    cx, cy = 337320.0, 3115840.0
    half_w = 2000.0
    xmin, xmax = cx - half_w, cx + half_w
    ymin, ymax = cy - half_w, cy + half_w

    fig, ax = plt.subplots(figsize=(10, 10), dpi=200)

    # Plot accurately georeferenced raster background
    npz_path = "data/interim/s2_cache/post_119_S2B_MSIL2A_20260827T045659_R11.npz"
    extent, _ = plot_raster_background(
        ax,
        npz_path,
        transform=trans,
        clip_extent=(xmin, xmax, ymin, ymax),
        zorder=1
    )

    # EMS Landslide footprint (yellow outline + fill)
    ems_clip = ems_gdf.clip_by_rect(xmin, ymin, xmax, ymax)
    ems_clip = ems_clip[~ems_clip.is_empty]
    if len(ems_clip) > 0:
        ems_clip.plot(ax=ax, facecolor=(1.0, 0.9, 0.0, 0.20), edgecolor="#ffe600", linewidth=2.2, zorder=3)

    # Our Layer 2 Class 2 & Class 3
    inv_trans = ~trans
    c1 = int(round((xmin - trans.c) / trans.a))
    r1 = int(round((ymax - trans.f) / trans.e))
    c2 = int(round((xmax - trans.c) / trans.a))
    r2 = int(round((ymin - trans.f) / trans.e))

    r_start = max(0, min(r1, r2, h))
    r_end = max(0, min(max(r1, r2), h))
    c_start = max(0, min(c1, c2, w))
    c_end = max(0, min(max(c1, c2), w))

    sub_c2 = (hazard_raster[r_start:r_end, c_start:c_end] == 2).astype(np.uint8)
    sub_c3 = (hazard_raster[r_start:r_end, c_start:c_end] == 3).astype(np.uint8)

    nx, ny = c_end - c_start, r_end - r_start
    X = np.linspace(extent[0], extent[1], nx)
    Y = np.linspace(extent[3], extent[2], ny)

    if np.sum(sub_c3) > 0:
        ax.contour(X, Y, sub_c3, levels=[0.5], colors=["#ff8800"], linewidths=1.8, linestyles="--", zorder=4)

    if np.sum(sub_c2) > 0:
        ax.contour(X, Y, sub_c2, levels=[0.5], colors=["#ff2200"], linewidths=2.0, zorder=5)
        c2_rgba = np.zeros((*sub_c2.shape, 4), dtype=np.float32)
        c2_rgba[sub_c2 == 1] = [1.0, 0.15, 0.0, 0.35]
        ax.imshow(c2_rgba, extent=extent, origin="upper", zorder=5)

    # AOI boundary
    aoi_clip = aoi_gdf.clip_by_rect(xmin, ymin, xmax, ymax)
    aoi_clip = aoi_clip[~aoi_clip.is_empty]
    if len(aoi_clip) > 0:
        aoi_clip.boundary.plot(ax=ax, color="#00ffff", linewidth=1.5, linestyle="--", zorder=6)

    # Built-in River Centreline Alignment Verification
    draw_osm_river_centreline(ax, target_crs=crs, clip_bounds=(xmin, ymin, xmax, ymax), color="#00e5ff", lw=1.2, zorder=12)

    # Town center
    ax.plot(cx, cy, "w*", markersize=14, markeredgecolor="black", markeredgewidth=1.5, zorder=15)
    ax.text(
        cx + 60, cy, "Syabru Besi\n(85.343°E, 28.161°N)",
        color="white", fontsize=10, fontweight="bold",
        bbox=dict(boxstyle="round,pad=0.25", facecolor="black", alpha=0.7, edgecolor="none"),
        zorder=15
    )

    ax.set_title(
        "Layer 3 Validation: Syabru Besi 4x4 km Zoom (Georeferenced Alignment)\n"
        "Sentinel-2 Post True Colour (2026-08-27) + River Alignment Check (cyan)",
        fontsize=12, fontweight="bold", pad=10
    )
    ax.axis("off")

    legend_elements = [
        Line2D([0], [0], color="#ffe600", lw=2.5, label="Copernicus EMS Landslide (EMSR927)"),
        Line2D([0], [0], color="#ff2200", lw=2.0, label="Our Layer 2 Flood/Debris (Class 2)"),
        Line2D([0], [0], color="#ff8800", lw=1.8, linestyle="--", label="Our Layer 2 Inferred (Class 3)"),
        Line2D([0], [0], color="#00e5ff", lw=1.2, label="OSM River Centreline (Alignment Check)"),
        Line2D([0], [0], color="#00ffff", lw=1.5, linestyle="--", label="EMS AOI Boundary"),
        Line2D([0], [0], marker="*", color="w", markeredgecolor="black", markersize=12, label="Syabru Besi Center", linestyle="None")
    ]
    ax.legend(handles=legend_elements, loc="lower left", framealpha=0.9, fontsize=9.5)

    plt.savefig(output_png, bbox_inches="tight")
    plt.close()
    print(f"Validation plot saved to {output_png}")


if __name__ == "__main__":
    run_validation()
