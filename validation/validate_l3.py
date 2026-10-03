"""
Layer 3 Validation: Copernicus EMS EMSR927 Evaluation.
Evaluates Layer 2 hazard detection outputs against Copernicus EMS EMSR927 (AOI01 Syabru Besi).
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
    gt_bool = ems_mask & eval_mask

    def calc_metrics(pred_bool, gt_bool, dx=10.0):
        tp = np.sum(pred_bool & gt_bool)
        fp = np.sum(pred_bool & (~gt_bool))
        fn = np.sum((~pred_bool) & gt_bool)

        iou_10m = tp / (tp + fp + fn) if (tp + fp + fn) > 0 else 0
        prec_10m = tp / (tp + fp) if (tp + fp) > 0 else 0
        rec_10m = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1_10m = 2 * prec_10m * rec_10m / (prec_10m + rec_10m) if (prec_10m + rec_10m) > 0 else 0

        dist_to_gt = distance_transform_edt(~gt_bool) * dx
        dist_to_pred = distance_transform_edt(~pred_bool) * dx
        tp_tol_pred = np.sum(pred_bool & (dist_to_gt <= 20.0))
        tp_tol_gt = np.sum(gt_bool & (dist_to_pred <= 20.0))
        prec_20m = tp_tol_pred / np.sum(pred_bool) if np.sum(pred_bool) > 0 else 0
        rec_20m = tp_tol_gt / np.sum(gt_bool) if np.sum(gt_bool) > 0 else 0
        f1_20m = 2 * prec_20m * rec_20m / (prec_20m + rec_20m) if (prec_20m + rec_20m) > 0 else 0
        iou_20m = tp_tol_pred / (np.sum(pred_bool) + np.sum(gt_bool) - tp_tol_gt) if (np.sum(pred_bool) + np.sum(gt_bool) - tp_tol_gt) > 0 else 0

        return {
            "strict": {"iou": iou_10m, "f1": f1_10m, "prec": prec_10m, "rec": rec_10m},
            "tol20m": {"iou": iou_20m, "f1": f1_20m, "prec": prec_20m, "rec": rec_20m},
            "pred_area_km2": np.sum(pred_bool) * (dx * dx) / 1e6
        }

    # (a) Observed only (Class 2)
    pred_obs = (hazard_raster == 2) & eval_mask
    m_obs = calc_metrics(pred_obs, gt_bool, dx)

    # (b) Observed + Inferred (Class 2 + Class 3)
    pred_comb = np.isin(hazard_raster, [2, 3]) & eval_mask
    m_comb = calc_metrics(pred_comb, gt_bool, dx)

    ems_eval_area_km2 = np.sum(gt_bool) * pixel_area_m2 / 1e6
    ems_total_area_km2 = np.sum(ems_mask & aoi_mask) * pixel_area_m2 / 1e6

    print("\n--- RESULTS ---")
    print(f"EMS Landslide in valid AOI: {ems_eval_area_km2:.4f} km² (Total: {ems_total_area_km2:.4f} km²)")
    print(f"(a) Observed only: Area={m_obs['pred_area_km2']:.4f} km²")
    print(f"    Strict 10m: IoU={m_obs['strict']['iou']:.4f}, F1={m_obs['strict']['f1']:.4f}, Prec={m_obs['strict']['prec']:.4f}, Rec={m_obs['strict']['rec']:.4f}")
    print(f"    Tolerant 20m: IoU={m_obs['tol20m']['iou']:.4f}, F1={m_obs['tol20m']['f1']:.4f}, Prec={m_obs['tol20m']['prec']:.4f}, Rec={m_obs['tol20m']['rec']:.4f}")
    print(f"(b) Observed + Inferred: Area={m_comb['pred_area_km2']:.4f} km²")
    print(f"    Strict 10m: IoU={m_comb['strict']['iou']:.4f}, F1={m_comb['strict']['f1']:.4f}, Prec={m_comb['strict']['prec']:.4f}, Rec={m_comb['strict']['rec']:.4f}")
    print(f"    Tolerant 20m: IoU={m_comb['tol20m']['iou']:.4f}, F1={m_comb['tol20m']['f1']:.4f}, Prec={m_comb['tol20m']['prec']:.4f}, Rec={m_comb['tol20m']['rec']:.4f}")

    # 6. Syabru Besi Overlay Plot
    data = np.load("data/interim/s2_cache/post_119_S2B_MSIL2A_20260827T045659_R11.npz")
    vis = data["visual"]
    r1, r2 = 792, 1192
    c1, c2 = 231, 631

    sub_vis = vis[:, r1:r2, c1:c2].transpose(1, 2, 0)
    sub_obs = (hazard_raster[r1:r2, c1:c2] == 2).astype(np.uint8)
    sub_inf = (hazard_raster[r1:r2, c1:c2] == 3).astype(np.uint8)
    sub_ems = ems_mask[r1:r2, c1:c2]
    sub_aoi = aoi_mask[r1:r2, c1:c2]

    fig, ax = plt.subplots(figsize=(11, 11), dpi=200)
    ax.imshow(sub_vis)

    # EMS Landslide: Yellow outline + translucent fill
    if np.sum(sub_ems) > 0:
        ax.contour(sub_ems, levels=[0.5], colors=["#ffe600"], linewidths=2.5)
        ems_rgba = np.zeros((*sub_ems.shape, 4), dtype=np.float32)
        ems_rgba[sub_ems == 1] = [1.0, 0.9, 0.0, 0.22]
        ax.imshow(ems_rgba)

    # Inferred Flooded (Class 3): Orange dashed outline + translucent fill
    if np.sum(sub_inf) > 0:
        ax.contour(sub_inf, levels=[0.5], colors=["#ff8800"], linewidths=2.0, linestyles="--")
        inf_rgba = np.zeros((*sub_inf.shape, 4), dtype=np.float32)
        inf_rgba[sub_inf == 1] = [1.0, 0.55, 0.0, 0.35]
        ax.imshow(inf_rgba)

    # Observed Affected (Class 2): Red outline + translucent fill
    if np.sum(sub_obs) > 0:
        ax.contour(sub_obs, levels=[0.5], colors=["#ff2200"], linewidths=2.2)
        obs_rgba = np.zeros((*sub_obs.shape, 4), dtype=np.float32)
        obs_rgba[sub_obs == 1] = [1.0, 0.15, 0.0, 0.40]
        ax.imshow(obs_rgba)

    # EMS AOI Boundary: Cyan dashed outline
    if np.sum(sub_aoi) > 0:
        ax.contour(sub_aoi, levels=[0.5], colors=["#00ffff"], linewidths=1.5, linestyles=":")

    town_r, town_c = 992 - r1, 431 - c1
    ax.plot(town_c, town_r, "w*", markersize=14, markeredgecolor="black", markeredgewidth=1.5)
    ax.text(
        town_c + 8, town_r, "Syabru Besi\n(85.343°E, 28.161°N)",
        color="white", fontsize=10, fontweight="bold",
        bbox=dict(boxstyle="round,pad=0.25", facecolor="black", alpha=0.7, edgecolor="none")
    )
    ax.set_title(
        "Layer 3 Validation: Syabru Besi 4x4 km Zoom\n"
        "Sentinel-2 Post True Colour (2026-08-27) + Copernicus EMS vs Observed (Red) & Inferred (Orange)",
        fontsize=12, fontweight="bold", pad=10
    )
    ax.axis("off")

    legend_elements = [
        Line2D([0], [0], color="#ffe600", lw=2.5, label=f"Copernicus EMS Landslide ({np.sum(gt_bool)*0.0001:.2f} km²)"),
        Line2D([0], [0], color="#ff2200", lw=2.2, label=f"Observed Class 2 ({m_obs['pred_area_km2']:.2f} km²)"),
        Line2D([0], [0], color="#ff8800", lw=2.0, linestyle="--", label=f"Inferred Class 3 ({(np.sum(pred_comb)-np.sum(pred_obs))*0.0001:.2f} km²)"),
        Line2D([0], [0], color="#00ffff", lw=1.5, linestyle=":", label="EMS AOI Boundary"),
        Line2D([0], [0], marker="*", color="w", markeredgecolor="black", markersize=12, label="Syabru Besi Center", linestyle="None")
    ]
    ax.legend(handles=legend_elements, loc="lower left", framealpha=0.9, fontsize=10)

    plt.savefig(output_png, bbox_inches="tight")
    plt.close()
    print(f"Validation plot saved to {output_png}")

    # Copy to artifact directory
    import shutil
    artifact_png = Path("/home/zeus/.gemini/antigravity/brain/52dd5215-6165-4f39-8912-cfce41bfdff1/quicklook_validation.png")
    shutil.copy2(output_png, artifact_png)
    print(f"Copied to artifact: {artifact_png}")


if __name__ == "__main__":
    run_validation()
