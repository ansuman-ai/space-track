"""
Ablation Study Runner for Layer 2 Variants.
Runs variants A through E:
A) l2.2 as is (old HAND, no built-up CVA, no intact-veg filter)
B) l2.2 + built-up CVA only
C) B + intact-vegetation filter
D) B + new HAND (pit fill / flat resolution)
E) all (= l2.3)

Outputs:
- EVENT affected km²
- EVENT inferred km²
- CONTROL affected+inferred km²
- L3 Metrics for (observed + inferred): IoU, F1, Precision, Recall (strict and 20m)
- 1 overlay plot per variant (Syabru Besi zoom)
"""

import os
import sys
import shutil
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import rasterio
from rasterio.features import rasterize
import geopandas as gpd
import numpy as np
from scipy.ndimage import distance_transform_edt
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

from src.common.plot_utils import (
    plot_raster_background,
    draw_osm_river_centreline,
    reproject_vector,
)

from src.l2_detection.s2_composite import prepare_s2_event_and_control_composites
from src.l2_detection.thresholds import (
    compute_s2_control_thresholds,
    compute_in_channel_control_threshold,
    compute_builtup_control_threshold,
    compute_s1_zscore_control_threshold
)
from src.l2_detection.water import detect_permanent_water
from src.l2_detection.run_l2 import load_s1_features, filter_stream_connected_blobs
from src.l2_detection.hydraulic_fill import compute_inferred_flood_corridor


def main():
    utm_crs = "EPSG:32645"
    out_dir = Path("validation")
    out_dir.mkdir(parents=True, exist_ok=True)
    artifact_dir = Path("/home/zeus/.gemini/antigravity/brain/52dd5215-6165-4f39-8912-cfce41bfdff1")

    # 1. Load Rasters and Masks
    with rasterio.open("data/interim/hand_old.tif") as f_ho, \
         rasterio.open("data/interim/stream_mask_old.tif") as f_so, \
         rasterio.open("data/interim/hand.tif") as f_hn, \
         rasterio.open("data/interim/stream_mask.tif") as f_sn, \
         rasterio.open("data/interim/shadow_layover_mask.tif") as f_sh, \
         rasterio.open("data/interim/nodata_mask.tif") as f_nd:

        hand_old = f_ho.read(1)
        stream_old = f_so.read(1)
        hand_new = f_hn.read(1)
        stream_new = f_sn.read(1)
        shadow_mask = f_sh.read(1)
        nodata_mask = f_nd.read(1)
        trans = f_ho.transform
        crs = f_ho.crs
        ref_profile = f_ho.profile.copy()
        h, w = hand_old.shape
        dx = abs(trans.a)

    pixel_area_km2 = (dx * dx) / 1e6

    # 2. S2 composites and differences
    s2_data = prepare_s2_event_and_control_composites("data/interim/s2_cache", 60.0, dx)
    pre_comp = s2_data["pre_composite"]
    post_comp = s2_data["post_composite"]
    ctrl_comp = s2_data["ctrl_post_composite"]
    d_ndvi_event = s2_data["d_ndvi_event"]
    d_bsi_event = s2_data["d_bsi_event"]
    s2_event_valid = s2_data["s2_event_valid"]
    d_ndvi_ctrl = s2_data["d_ndvi_ctrl"]
    d_bsi_ctrl = s2_data["d_bsi_ctrl"]
    s2_ctrl_valid = s2_data["s2_ctrl_valid"]

    # 3. S1 features
    s1_data = load_s1_features(Path("data/raw/s1_stack"), Path("data/interim/s1_cache"), Path("data/raw/s1/post.tif"))
    z_vv_asc_event = s1_data["z_vv_asc_event"]
    z_vv_asc_ctrl = s1_data["z_vv_asc_ctrl"]
    o19_lr_event = s1_data["o19_lr_event"]
    post_vv = s1_data["post_vv"]

    # 4. Built-up Mask & CVM
    band_keys = ['b02', 'b03', 'b04', 'b08', 'b11', 'b12']
    sq_ev = sum([((post_comp[b] - pre_comp[b]) / 10000.0) ** 2 for b in band_keys])
    cvm_ev = np.sqrt(sq_ev).astype(np.float32)
    sq_ctrl = sum([((ctrl_comp[b] - pre_comp[b]) / 10000.0) ** 2 for b in band_keys])
    cvm_ctrl = np.sqrt(sq_ctrl).astype(np.float32)

    b_gdf = gpd.read_file("data/raw/osm/osm_buildings.geojson").to_crs(crs)
    b_geoms = [geom.buffer(10.0) for geom in b_gdf.geometry if geom is not None and not geom.is_empty]
    builtup_mask = rasterize(b_geoms, out_shape=(h, w), transform=trans, fill=0, default_value=1, dtype=np.uint8)

    # 5. EMS Ground Truth for L3
    ems_dir = Path("validation/emsr927")
    aoi_gdf = gpd.read_file(ems_dir / "EMSR927_AOI01_GRA_PRODUCT_areaOfInterestA_v1.shp").to_crs(crs)
    aoi_mask = rasterize([(g, 1) for g in aoi_gdf.geometry], out_shape=(h, w), transform=trans, fill=0, dtype=np.uint8) == 1

    ems_gdf = gpd.read_file(ems_dir / "EMSR927_AOI01_GRA_PRODUCT_observedEventA_v1.shp").to_crs(crs)
    ems_mask = rasterize([(g, 1) for g in ems_gdf.geometry], out_shape=(h, w), transform=trans, fill=0, dtype=np.uint8) == 1

    eval_mask = aoi_mask & s2_event_valid
    gt_bool = ems_mask & eval_mask

    # 6. S2 visual background for plot
    data_vis = np.load("data/interim/s2_cache/post_119_S2B_MSIL2A_20260827T045659_R11.npz")
    vis = data_vis["visual"]
    r1, r2 = 792, 1192
    c1, c2 = 231, 631
    sub_vis = vis[:, r1:r2, c1:c2].transpose(1, 2, 0)

    cx, cy = 337320.0, 3115840.0
    half_w = 2000.0
    xmin, xmax = cx - half_w, cx + half_w
    ymin, ymax = cy - half_w, cy + half_w
    extent = [xmin, xmax, ymin, ymax]

    variants = [
        {"id": "A", "label": "l2.2 as is", "hand_type": "old", "builtup": False, "intact_filter": False},
        {"id": "B", "label": "l2.2 + built-up CVA only", "hand_type": "old", "builtup": True, "intact_filter": False},
        {"id": "C", "label": "B + intact-vegetation filter", "hand_type": "old", "builtup": True, "intact_filter": True},
        {"id": "D", "label": "B + new HAND (pit fill / flat res)", "hand_type": "new", "builtup": True, "intact_filter": False},
        {"id": "E", "label": "all (= l2.3)", "hand_type": "new", "builtup": True, "intact_filter": True},
    ]

    results = []

    for v in variants:
        vid = v["id"]
        vlabel = v["label"]
        hand = hand_old if v["hand_type"] == "old" else hand_new
        stream = stream_old if v["hand_type"] == "old" else stream_new

        # Baseline permanent water for this hand
        perm_water_raw, _ = detect_permanent_water(
            pre_vv=post_vv,
            hand=hand,
            shadow_mask=shadow_mask,
            osm_waterways_path="data/raw/osm/osm_waterways.geojson",
            transform_matrix=trans,
            crs=crs,
            hand_corridor_m=15.0,
            pre_ndwi=pre_comp["ndwi"]
        )

        # Thresholds
        t_d_ndvi, t_d_bsi = compute_s2_control_thresholds(d_ndvi_ctrl, d_bsi_ctrl, s2_ctrl_valid, hand, 40.0, 1.0)
        t_channel = compute_in_channel_control_threshold(s2_data["in_channel_change_ctrl"], perm_water_raw, s2_ctrl_valid, hand, 40.0, 1.0)
        t_z_asc = compute_s1_zscore_control_threshold(z_vv_asc_ctrl, hand, shadow_mask, nodata_mask, 40.0, 1.0)
        t_lr_o19 = -3.5

        if v["builtup"]:
            t_builtup = compute_builtup_control_threshold(cvm_ctrl, builtup_mask, s2_ctrl_valid, hand, 40.0, 1.0)
        else:
            t_builtup = 999.0

        hand_corridor = (hand <= 40.0) & (hand >= 0)

        # EVENT detection
        s2_ev = s2_event_valid & ((d_ndvi_event < t_d_ndvi) | (d_bsi_event > t_d_bsi)) & hand_corridor
        ch_ev = s2_event_valid & (perm_water_raw == 1) & hand_corridor & (s2_data["in_channel_change_event"] > t_channel)
        s1_ev = (~s2_event_valid) & ((z_vv_asc_event < t_z_asc) | (o19_lr_event < t_lr_o19)) & hand_corridor & (shadow_mask == 0) & (nodata_mask == 0)
        if v["builtup"]:
            b_ev = s2_event_valid & (builtup_mask == 1) & hand_corridor & (cvm_ev > t_builtup)
            ev_cand = (s2_ev | ch_ev | s1_ev | b_ev).astype(np.uint8)
        else:
            ev_cand = (s2_ev | ch_ev | s1_ev).astype(np.uint8)

        aff_ev_clean, _ = filter_stream_connected_blobs(ev_cand, stream, dx, 100.0, 20)

        # Inferred flood corridor
        if v["intact_filter"]:
            inferred_ev, _ = compute_inferred_flood_corridor(
                hand=hand,
                stream_mask=stream,
                observed_class2_mask=(aff_ev_clean == 1),
                pixel_size_m=dx,
                reach_length_m=250.0,
                hand_percentile=90.0,
                min_observed_pixels=20,
                touch_distance_m=100.0,
                max_hand_corridor_m=40.0,
                post_ndvi=post_comp["ndvi"],
                d_ndvi=d_ndvi_event,
                intact_min_post_ndvi=0.40,
                intact_max_abs_d_ndvi=0.20
            )
        else:
            inferred_ev, _ = compute_inferred_flood_corridor(
                hand=hand,
                stream_mask=stream,
                observed_class2_mask=(aff_ev_clean == 1),
                pixel_size_m=dx,
                reach_length_m=250.0,
                hand_percentile=90.0,
                min_observed_pixels=20,
                touch_distance_m=100.0,
                max_hand_corridor_m=40.0,
                post_ndvi=None,
                d_ndvi=None
            )

        # CONTROL detection
        s2_ctrl = s2_ctrl_valid & ((d_ndvi_ctrl < t_d_ndvi) | (d_bsi_ctrl > t_d_bsi)) & hand_corridor
        ch_ctrl = s2_ctrl_valid & (perm_water_raw == 1) & hand_corridor & (s2_data["in_channel_change_ctrl"] > t_channel)
        s1_ctrl = (~s2_ctrl_valid) & (z_vv_asc_ctrl < t_z_asc) & hand_corridor & (shadow_mask == 0) & (nodata_mask == 0)
        if v["builtup"]:
            b_ctrl = s2_ctrl_valid & (builtup_mask == 1) & hand_corridor & (cvm_ctrl > t_builtup)
            ctrl_cand = (s2_ctrl | ch_ctrl | s1_ctrl | b_ctrl).astype(np.uint8)
        else:
            ctrl_cand = (s2_ctrl | ch_ctrl | s1_ctrl).astype(np.uint8)

        aff_ctrl_clean, _ = filter_stream_connected_blobs(ctrl_cand, stream, dx, 100.0, 20)

        if v["intact_filter"]:
            inferred_ctrl, _ = compute_inferred_flood_corridor(
                hand=hand,
                stream_mask=stream,
                observed_class2_mask=(aff_ctrl_clean == 1),
                pixel_size_m=dx,
                reach_length_m=250.0,
                hand_percentile=90.0,
                min_observed_pixels=20,
                touch_distance_m=100.0,
                max_hand_corridor_m=40.0,
                post_ndvi=ctrl_comp["ndvi"],
                d_ndvi=d_ndvi_ctrl,
                intact_min_post_ndvi=0.40,
                intact_max_abs_d_ndvi=0.20
            )
        else:
            inferred_ctrl, _ = compute_inferred_flood_corridor(
                hand=hand,
                stream_mask=stream,
                observed_class2_mask=(aff_ctrl_clean == 1),
                pixel_size_m=dx,
                reach_length_m=250.0,
                hand_percentile=90.0,
                min_observed_pixels=20,
                touch_distance_m=100.0,
                max_hand_corridor_m=40.0,
                post_ndvi=None,
                d_ndvi=None
            )

        ev_aff_km2 = float(np.sum(aff_ev_clean == 1) * pixel_area_km2)
        ev_inf_km2 = float(np.sum(inferred_ev == 1) * pixel_area_km2)
        ctrl_aff_km2 = float(np.sum(aff_ctrl_clean == 1) * pixel_area_km2)
        ctrl_inf_km2 = float(np.sum(inferred_ctrl == 1) * pixel_area_km2)
        ctrl_tot_km2 = ctrl_aff_km2 + ctrl_inf_km2

        # Synthesize and save full hazard classes GeoTIFF for this variant
        hazard_raster = np.zeros((h, w), dtype=np.uint8)
        hazard_raster[perm_water_raw == 1] = 1
        hazard_raster[inferred_ev == 1] = 3
        hazard_raster[aff_ev_clean == 1] = 2

        tif_path = out_dir / f"hazard_classes_{vid}.tif"
        p_out = ref_profile.copy()
        p_out.update(driver="GTiff", count=1, dtype="uint8", nodata=0, compress="lzw")
        with rasterio.open(tif_path, "w", **p_out) as dst_tif:
            dst_tif.write(hazard_raster, 1)

        # L3 Metrics (Observed + Inferred)
        pred_both = ((aff_ev_clean == 1) | (inferred_ev == 1)) & eval_mask

        # Strict 10m
        tp = np.sum(pred_both & gt_bool)
        fp = np.sum(pred_both & (~gt_bool))
        fn = np.sum((~pred_both) & gt_bool)

        iou_10m = float(tp / (tp + fp + fn)) if (tp + fp + fn) > 0 else 0.0
        prec_10m = float(tp / (tp + fp)) if (tp + fp) > 0 else 0.0
        rec_10m = float(tp / (tp + fn)) if (tp + fn) > 0 else 0.0
        f1_10m = float(2 * prec_10m * rec_10m / (prec_10m + rec_10m)) if (prec_10m + rec_10m) > 0 else 0.0

        # Tolerant 20m
        dist_gt = distance_transform_edt(~gt_bool) * dx
        dist_pred = distance_transform_edt(~pred_both) * dx
        tp_tol_pred = np.sum(pred_both & (dist_gt <= 20.0))
        tp_tol_gt = np.sum(gt_bool & (dist_pred <= 20.0))

        prec_20m = float(tp_tol_pred / np.sum(pred_both)) if np.sum(pred_both) > 0 else 0.0
        rec_20m = float(tp_tol_gt / np.sum(gt_bool)) if np.sum(gt_bool) > 0 else 0.0
        f1_20m = float(2 * prec_20m * rec_20m / (prec_20m + rec_20m)) if (prec_20m + rec_20m) > 0 else 0.0
        denom_20m = (np.sum(pred_both) + np.sum(gt_bool) - tp_tol_gt)
        iou_20m = float(tp_tol_pred / denom_20m) if denom_20m > 0 else 0.0

        res_dict = {
            "variant": vid,
            "label": vlabel,
            "ev_aff_km2": ev_aff_km2,
            "ev_inf_km2": ev_inf_km2,
            "ctrl_tot_km2": ctrl_tot_km2,
            "strict": {"iou": iou_10m, "f1": f1_10m, "prec": prec_10m, "rec": rec_10m},
            "tol20m": {"iou": iou_20m, "f1": f1_20m, "prec": prec_20m, "rec": rec_20m}
        }
        results.append(res_dict)

        # Plot overlay for this variant using unified plot_utils
        fig, ax = plt.subplots(figsize=(10, 10), dpi=180)
        ext_v, _ = plot_raster_background(ax, data_vis["visual"], transform=trans, clip_extent=(xmin, xmax, ymin, ymax), zorder=1)
        draw_osm_river_centreline(ax, target_crs=crs, clip_bounds=(xmin, ymin, xmax, ymax), color="#00e5ff", lw=1.2, zorder=12)

        # EMS Landslide footprint (yellow outline)
        ems_ev_clip = ems_gdf.clip_by_rect(xmin, ymin, xmax, ymax)
        ems_ev_clip = ems_ev_clip[~ems_ev_clip.is_empty]
        if len(ems_ev_clip) > 0:
            ems_ev_clip.plot(ax=ax, facecolor=(1.0, 0.9, 0.0, 0.12), edgecolor="#ffe600", linewidth=2.2, zorder=3)

        # Rasterize and contour Class 2 & Class 3 in sub-region
        inv_trans = ~trans
        c1_idx = int(round((xmin - trans.c) / trans.a))
        r1_idx = int(round((ymax - trans.f) / trans.e))
        c2_idx = int(round((xmax - trans.c) / trans.a))
        r2_idx = int(round((ymin - trans.f) / trans.e))
        r_start = max(0, min(r1_idx, r2_idx, h))
        r_end = max(0, min(max(r1_idx, r2_idx), h))
        c_start = max(0, min(c1_idx, c2_idx, w))
        c_end = max(0, min(max(c1_idx, c2_idx), w))

        sub_c2 = (aff_ev_clean == 1)[r_start:r_end, c_start:c_end]
        sub_c3 = (inferred_ev == 1)[r_start:r_end, c_start:c_end]

        nx, ny = c_end - c_start, r_end - r_start
        X = np.linspace(ext_v[0], ext_v[1], nx)
        Y = np.linspace(ext_v[3], ext_v[2], ny)

        if np.any(sub_c3):
            ax.contour(X, Y, sub_c3, levels=[0.5], colors=["#ff8800"], linewidths=[1.8], linestyles=["--"], zorder=4)
        if np.any(sub_c2):
            ax.contour(X, Y, sub_c2, levels=[0.5], colors=["#ff2200"], linewidths=[2.0], linestyles=["-"], zorder=5)

        ax.plot(cx, cy, marker="*", color="white", markeredgecolor="black", markersize=13)
        ax.text(
            cx + 60, cy, "Syabru Besi",
            color="white", fontsize=10, fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.2", facecolor="black", alpha=0.75, edgecolor="none")
        )

        ax.set_xlim(xmin, xmax)
        ax.set_ylim(ymin, ymax)
        ax.axis("off")

        legend_elements = [
            Line2D([0], [0], color="#ffe600", lw=2.2, label="EMS Landslide / Debris (EMSR927)"),
            Line2D([0], [0], color="#00e5ff", lw=1.2, label="OSM River Centreline (Alignment Check)"),
            Line2D([0], [0], color="#ff2200", lw=2.0, label=f"Observed Class 2 ({ev_aff_km2:.3f} km²)"),
            Line2D([0], [0], color="#ff8800", lw=1.8, linestyle="--", label=f"Inferred Class 3 ({ev_inf_km2:.3f} km²)"),
            Line2D([0], [0], marker="*", color="w", markeredgecolor="black", markersize=11, label="Syabru Besi Center", linestyle="None")
        ]
        ax.legend(handles=legend_elements, loc="lower left", framealpha=0.92, fontsize=9.2)

        ax.set_title(
            f"Variant {vid}: {vlabel}\n"
            f"Strict IoU={iou_10m:.3f}, F1={f1_10m:.3f} | 20m IoU={iou_20m:.3f}, F1={f1_20m:.3f} | Ctrl={ctrl_tot_km2:.3f} km²",
            fontsize=11.0, fontweight="bold", pad=10
        )

        plot_path = out_dir / f"overlay_ablation_{vid}.png"
        plt.savefig(plot_path, bbox_inches="tight")
        plt.close()

        # Copy to artifact
        art_path = artifact_dir / f"overlay_ablation_{vid}.png"
        shutil.copy2(plot_path, art_path)
        print(f"Saved plot for Variant {vid}: {plot_path}")

    # Print summary table
    print("\n========================= ABLATION RESULTS =========================")
    for r in results:
        vid = r["variant"]
        lbl = r["label"]
        ev_aff = r["ev_aff_km2"]
        ev_inf = r["ev_inf_km2"]
        ctrl = r["ctrl_tot_km2"]
        s = r["strict"]
        t = r["tol20m"]
        print(f"{vid}) {lbl:32s} | EvAff: {ev_aff:.3f} km² | EvInf: {ev_inf:.3f} km² | Ctrl: {ctrl:.3f} km² | "
              f"Strict(IoU={s['iou']:.3f}, F1={s['f1']:.3f}, P={s['prec']:.3f}, R={s['rec']:.3f}) | "
              f"20m(IoU={t['iou']:.3f}, F1={t['f1']:.3f}, P={t['prec']:.3f}, R={t['rec']:.3f})")


if __name__ == "__main__":
    main()
