"""
Layer 2 Quick-look Visualization Generator.
Generates full AOI hazard classification map and high-resolution 4x4 km zoom
with Sentinel-2 Post True Colour and affected class outline, using unified plot_utils
and built-in pre-event OSM river centreline alignment verification.
"""

import os
from typing import Dict, Any, Optional, Tuple
import numpy as np
import rasterio
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap, BoundaryNorm
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D

from src.common.plot_utils import (
    plot_raster_background,
    draw_osm_river_centreline,
    reproject_vector,
)


def render_layer2_quicklook(
    post_vv: np.ndarray,
    hazard_raster: np.ndarray,
    output_png_path: str,
    stats: Dict[str, Any],
    post_vis: Optional[np.ndarray] = None,
    zoom_center: Optional[Tuple[int, int]] = None,
    transform_matrix: Any = None
) -> str:
    """
    Renders 2-panel figure with unified georeferencing and OSM river alignment check:
    - Panel 1: Full AOI hazard classification map
    - Panel 2: High-impact 4x4 km zoom with S2 Post True Colour, outlines, and river alignment
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_png_path)), exist_ok=True)

    if transform_matrix is None:
        ref_path = "data/processed/hazard_classes.tif"
        if os.path.exists(ref_path):
            with rasterio.open(ref_path) as src:
                transform_matrix = src.transform

    fig, axes = plt.subplots(1, 2, figsize=(22, 11), constrained_layout=True)

    # Colormap: 0=transparent, 1=blue (Permanent Water), 2=red/amber (Observed Affected), 3=orange (Inferred Flooded)
    colors = [
        (0.0, 0.0, 0.0, 0.0),       # 0: Background
        (0.12, 0.45, 0.95, 0.85),   # 1: Permanent Water
        (0.98, 0.15, 0.08, 0.90),   # 2: Observed Flood / Debris Affected
        (1.0, 0.55, 0.0, 0.85),     # 3: Inferred Flooded
    ]
    cmap = ListedColormap(colors)
    norm = BoundaryNorm([-0.5, 0.5, 1.5, 2.5, 3.5], 4)

    h, w = hazard_raster.shape

    # --- Panel 1: Full AOI ---
    if transform_matrix is not None:
        if post_vis is not None:
            extent_full, _ = plot_raster_background(axes[0], post_vis, transform=transform_matrix, zorder=1)
        else:
            extent_full, _ = plot_raster_background(axes[0], post_vv, transform=transform_matrix, cmap="gray", vmin=-25.0, vmax=5.0, zorder=1)
        axes[0].imshow(hazard_raster, cmap=cmap, norm=norm, interpolation="nearest", extent=extent_full, zorder=2)
        draw_osm_river_centreline(axes[0], zorder=10, lw=0.9, alpha=0.7)
    else:
        if post_vis is not None:
            vis_rgb = post_vis.transpose(1, 2, 0) if post_vis.shape[0] == 3 else post_vis
            axes[0].imshow(vis_rgb)
        else:
            axes[0].imshow(post_vv, cmap="gray", vmin=-25.0, vmax=5.0)
        axes[0].imshow(hazard_raster, cmap=cmap, norm=norm, interpolation="nearest")

    # Dynamic spatial coordinates for 4x4 km zoom around highest impact area or center
    half_w = 2000.0
    if transform_matrix is not None:
        c2_r, c2_c = np.where(hazard_raster == 2)
        if len(c2_r) > 0:
            cx, cy = transform_matrix * (float(np.median(c2_c)), float(np.median(c2_r)))
        else:
            cx = (extent_full[0] + extent_full[1]) / 2.0 if 'extent_full' in locals() else 0.0
            cy = (extent_full[2] + extent_full[3]) / 2.0 if 'extent_full' in locals() else 0.0
    else:
        cx, cy = 0.0, 0.0
    xmin, xmax = cx - half_w, cx + half_w
    ymin, ymax = cy - half_w, cy + half_w

    if transform_matrix is not None:
        rect = plt.Rectangle((xmin, ymin), xmax - xmin, ymax - ymin, fill=False, edgecolor="yellow", linewidth=2.0, linestyle="--", zorder=12)
        axes[0].add_patch(rect)
        axes[0].text(xmin + 100, ymax - 200, "High-Impact 4x4km Zoom", color="yellow", fontsize=11, fontweight="bold", zorder=12)
    else:
        cr, cc = zoom_center if zoom_center is not None else (h // 2, w // 2)
        r1, r2 = max(0, cr - 200), min(h, cr + 200)
        c1, c2 = max(0, cc - 200), min(w, cc + 200)
        rect = plt.Rectangle((c1, r1), c2 - c1, r2 - r1, fill=False, edgecolor="yellow", linewidth=2.0, linestyle="--")
        axes[0].add_patch(rect)

    opt_note = stats.get("optical_evidence_note", "")
    p1_title = (
        f"Full AOI Hazard Classification ({w}x{h})\n"
        f"Permanent Water: {stats.get('perm_water_km2', 0):.3f} km² | "
        f"Observed: {stats.get('affected_km2', 0):.3f} km² | "
        f"Inferred: {stats.get('inferred_km2', 0):.3f} km²"
    )
    if opt_note:
        p1_title += f"\n[{opt_note}]"
    axes[0].set_title(p1_title, fontsize=13, fontweight="bold")
    axes[0].axis("off")

    legend_patches = [
        mpatches.Patch(color=(0.12, 0.45, 0.95, 0.85), label=f"Class 1: Permanent Water ({stats.get('perm_water_km2', 0):.3f} km²)"),
        mpatches.Patch(color=(0.98, 0.15, 0.08, 0.90), label=f"Class 2: Observed Affected ({stats.get('affected_km2', 0):.3f} km²)"),
        mpatches.Patch(color=(1.0, 0.55, 0.0, 0.85), label=f"Class 3: Inferred Flooded ({stats.get('inferred_km2', 0):.3f} km²)"),
        Line2D([0], [0], color="#00e5ff", lw=1.0, label="OSM River Centreline (Alignment Check)")
    ]
    axes[0].legend(handles=legend_patches, loc="lower left", framealpha=0.9, fontsize=10.5)

    # --- Panel 2: High-Impact 4x4 km Zoom with S2 Post True Colour + Outlines ---
    if transform_matrix is not None:
        bg_source = post_vis if post_vis is not None else post_vv
        cmap_arg = None if post_vis is not None else "gray"
        extent_zoom, _ = plot_raster_background(
            axes[1],
            bg_source,
            transform=transform_matrix,
            clip_extent=(xmin, xmax, ymin, ymax),
            cmap=cmap_arg,
            vmin=-25.0 if post_vis is None else None,
            vmax=5.0 if post_vis is None else None,
            zorder=1
        )

        # Slice hazard raster using transform
        inv_trans = ~transform_matrix
        c1_idx = int(round((xmin - transform_matrix.c) / transform_matrix.a))
        r1_idx = int(round((ymax - transform_matrix.f) / transform_matrix.e))
        c2_idx = int(round((xmax - transform_matrix.c) / transform_matrix.a))
        r2_idx = int(round((ymin - transform_matrix.f) / transform_matrix.e))

        r_start = max(0, min(r1_idx, r2_idx, h))
        r_end = max(0, min(max(r1_idx, r2_idx), h))
        c_start = max(0, min(c1_idx, c2_idx, w))
        c_end = max(0, min(max(c1_idx, c2_idx), w))

        sub_aff = (hazard_raster[r_start:r_end, c_start:c_end] == 2).astype(np.uint8)
        sub_inf = (hazard_raster[r_start:r_end, c_start:c_end] == 3).astype(np.uint8)
        sub_wat = (hazard_raster[r_start:r_end, c_start:c_end] == 1).astype(np.uint8)

        # Coordinates for contours
        nx, ny = c_end - c_start, r_end - r_start
        X = np.linspace(extent_zoom[0], extent_zoom[1], nx)
        Y = np.linspace(extent_zoom[3], extent_zoom[2], ny)

        if np.sum(sub_inf) > 0:
            axes[1].contour(X, Y, sub_inf, levels=[0.5], colors=['#ff8800'], linewidths=1.8, linestyles='--', zorder=3)
            inf_rgba = np.zeros((*sub_inf.shape, 4), dtype=np.float32)
            inf_rgba[sub_inf == 1] = [1.0, 0.55, 0.0, 0.35]
            axes[1].imshow(inf_rgba, extent=extent_zoom, origin="upper", zorder=3)

        if np.sum(sub_aff) > 0:
            axes[1].contour(X, Y, sub_aff, levels=[0.5], colors=['#ff2200'], linewidths=2.2, zorder=4)
            aff_rgba = np.zeros((*sub_aff.shape, 4), dtype=np.float32)
            aff_rgba[sub_aff == 1] = [1.0, 0.15, 0.0, 0.40]
            axes[1].imshow(aff_rgba, extent=extent_zoom, origin="upper", zorder=4)

        if np.sum(sub_wat) > 0:
            axes[1].contour(X, Y, sub_wat, levels=[0.5], colors=['#00c0ff'], linewidths=1.8, zorder=5)

        # Built-in river alignment check on zoom
        draw_osm_river_centreline(axes[1], clip_bounds=(xmin, ymin, xmax, ymax), zorder=12, lw=1.2, color="#00e5ff")

        # Town / impact center
        axes[1].plot(cx, cy, 'w*', markersize=14, markeredgecolor='black', markeredgewidth=1.5, zorder=15)
        axes[1].text(
            cx + 60, cy, "Zoom Center",
            color="white", fontsize=11, fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.25", facecolor="black", alpha=0.75, edgecolor="none"),
            zorder=15
        )

    p2_title = (
        "High-Impact 4x4 km Zoom (Aligned S2/SAR Post Composite)\n"
        "Observed (red) & Inferred (orange) Outlines + River Alignment Check (cyan)"
    )
    if opt_note:
        p2_title += f"\n[{opt_note}]"
    axes[1].set_title(p2_title, fontsize=13, fontweight="bold")
    axes[1].axis("off")

    zoom_aff_km2 = np.sum(hazard_raster == 2) * 0.0001
    zoom_inf_km2 = np.sum(hazard_raster == 3) * 0.0001
    zoom_legend = [
        Line2D([0], [0], color='#ff2200', lw=2.5, label="Class 2: Observed Damage"),
        Line2D([0], [0], color='#ff8800', lw=2.0, linestyle='--', label="Class 3: Inferred Flooded"),
        Line2D([0], [0], color='#00e5ff', lw=1.2, label="OSM River Centreline (Alignment Check)"),
        Line2D([0], [0], marker='*', color='w', markeredgecolor='black', markersize=12, label="Zoom Center", linestyle="None")
    ]
    axes[1].legend(handles=zoom_legend, loc="lower left", framealpha=0.9, fontsize=10.5)

    supt = "Layer 2 Final Hazard Detection: Sentinel-2 Optical Primary + Sentinel-1 SAR Fallback"
    if opt_note:
        supt += f"\n({opt_note})"
    fig.suptitle(supt, fontsize=16, fontweight="bold", y=1.02)

    plt.savefig(output_png_path, dpi=200, bbox_inches="tight")
    plt.close(fig)

    # Also render standalone zoom image
    zoom_only_path = output_png_path.replace("quicklook_layer2.png", "quicklook_zoom.png")
    if zoom_only_path != output_png_path:
        fig_z, ax_z = plt.subplots(figsize=(10, 10), constrained_layout=True)
        if transform_matrix is not None:
            plot_raster_background(
                ax_z,
                bg_source,
                transform=transform_matrix,
                clip_extent=(xmin, xmax, ymin, ymax),
                cmap=cmap_arg,
                zorder=1
            )
            if np.sum(sub_inf) > 0:
                ax_z.contour(X, Y, sub_inf, levels=[0.5], colors=['#ff8800'], linewidths=1.8, linestyles='--', zorder=3)
                ax_z.imshow(inf_rgba, extent=extent_zoom, origin="upper", zorder=3)
            if np.sum(sub_aff) > 0:
                ax_z.contour(X, Y, sub_aff, levels=[0.5], colors=['#ff2200'], linewidths=2.2, zorder=4)
                ax_z.imshow(aff_rgba, extent=extent_zoom, origin="upper", zorder=4)
            draw_osm_river_centreline(ax_z, clip_bounds=(xmin, ymin, xmax, ymax), zorder=12, lw=1.2, color="#00e5ff")
            ax_z.plot(cx, cy, 'w*', markersize=14, markeredgecolor='black', markeredgewidth=1.5, zorder=15)
            ax_z.text(
                cx + 60, cy, "Zoom Center",
                color="white", fontsize=11, fontweight="bold",
                bbox=dict(boxstyle="round,pad=0.25", facecolor="black", alpha=0.75, edgecolor="none"),
                zorder=15
            )
        z_title = "Layer 2 Detection: High-Impact 4x4 km Zoom (Aligned)\nPost Optical/SAR Composite + River Alignment Check"
        if opt_note:
            z_title += f"\n[{opt_note}]"
        ax_z.set_title(z_title, fontsize=13, fontweight="bold", pad=10)
        ax_z.axis("off")
        plt.close(fig_z)

    return output_png_path
