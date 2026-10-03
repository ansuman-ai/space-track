"""
Layer 2 Quick-look Visualization Generator.
Generates full AOI hazard classification map and high-resolution Syabru Besi 4x4 km zoom
with Sentinel-2 Post True Colour and affected class outline.
"""

import os
from typing import Dict, Any, Optional, Tuple
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap, BoundaryNorm
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D


def render_layer2_quicklook(
    post_vv: np.ndarray,
    hazard_raster: np.ndarray,
    output_png_path: str,
    stats: Dict[str, Any],
    post_vis: Optional[np.ndarray] = None,
    zoom_center: Tuple[int, int] = (992, 431)
) -> str:
    """
    Renders 2-panel figure:
    - Panel 1: Full AOI hazard classification map
    - Panel 2: Syabru Besi 4x4 km zoom with S2 Post True Colour and affected outline
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_png_path)), exist_ok=True)

    fig, axes = plt.subplots(1, 2, figsize=(22, 11), constrained_layout=True)

    # Colormap: 0=transparent, 1=blue (Permanent Water), 2=amber/orange (Flood/Debris Affected)
    colors = [
        (0.0, 0.0, 0.0, 0.0),       # 0: Background
        (0.12, 0.45, 0.95, 0.85),   # 1: Permanent Water
        (0.98, 0.35, 0.08, 0.90),   # 2: Flood / Debris Affected
    ]
    cmap = ListedColormap(colors)
    norm = BoundaryNorm([-0.5, 0.5, 1.5, 2.5], 3)

    h, w = hazard_raster.shape

    # --- Panel 1: Full AOI ---
    if post_vis is not None:
        if post_vis.shape[0] == 3:
            vis_rgb = post_vis.transpose(1, 2, 0)
        else:
            vis_rgb = post_vis
        axes[0].imshow(vis_rgb)
    else:
        axes[0].imshow(post_vv, cmap="gray", vmin=-25.0, vmax=5.0)

    axes[0].imshow(hazard_raster, cmap=cmap, norm=norm, interpolation="nearest")

    # Zoom box rectangle outline on Panel 1
    cr, cc = zoom_center
    r1, r2 = max(0, cr - 200), min(h, cr + 200)
    c1, c2 = max(0, cc - 200), min(w, cc + 200)
    rect = plt.Rectangle((c1, r1), c2 - c1, r2 - r1, fill=False, edgecolor="yellow", linewidth=2.0, linestyle="--")
    axes[0].add_patch(rect)
    axes[0].text(c1 + 10, r1 + 30, "Syabru Besi 4x4km Zoom", color="yellow", fontsize=11, fontweight="bold")

    axes[0].set_title(
        f"Full AOI Hazard Classification ({w}x{h})\n"
        f"Permanent Water: {stats.get('perm_water_km2', 0):.3f} km² | "
        f"Flood/Debris Affected: {stats.get('affected_km2', 0):.3f} km²",
        fontsize=13, fontweight="bold"
    )
    axes[0].axis("off")

    legend_patches = [
        mpatches.Patch(color=(0.12, 0.45, 0.95, 0.85), label=f"Class 1: Permanent Water ({stats.get('perm_water_km2', 0):.3f} km²)"),
        mpatches.Patch(color=(0.98, 0.35, 0.08, 0.90), label=f"Class 2: Flood / Debris Affected ({stats.get('affected_km2', 0):.3f} km²)"),
    ]
    axes[0].legend(handles=legend_patches, loc="lower left", framealpha=0.9, fontsize=11)

    # --- Panel 2: Syabru Besi 4x4 km Zoom with S2 Post True Colour + Affected Outline ---
    sub_aff = (hazard_raster[r1:r2, c1:c2] == 2).astype(np.uint8)
    sub_wat = (hazard_raster[r1:r2, c1:c2] == 1).astype(np.uint8)

    if post_vis is not None:
        if post_vis.shape[0] == 3:
            sub_vis = post_vis[:, r1:r2, c1:c2].transpose(1, 2, 0)
        else:
            sub_vis = post_vis[r1:r2, c1:c2]
        axes[1].imshow(sub_vis)
    else:
        axes[1].imshow(post_vv[r1:r2, c1:c2], cmap="gray", vmin=-25.0, vmax=5.0)

    # Contours & Translucent Fill
    if np.sum(sub_aff) > 0:
        axes[1].contour(sub_aff, levels=[0.5], colors=['#ff2200'], linewidths=2.2)
        aff_rgba = np.zeros((*sub_aff.shape, 4), dtype=np.float32)
        aff_rgba[sub_aff == 1] = [1.0, 0.2, 0.0, 0.40]
        axes[1].imshow(aff_rgba)

    if np.sum(sub_wat) > 0:
        axes[1].contour(sub_wat, levels=[0.5], colors=['#00c0ff'], linewidths=1.8)
        wat_rgba = np.zeros((*sub_wat.shape, 4), dtype=np.float32)
        wat_rgba[sub_wat == 1] = [0.0, 0.4, 1.0, 0.35]
        axes[1].imshow(wat_rgba)

    # Town center
    town_r, town_c = cr - r1, cc - c1
    axes[1].plot(town_c, town_r, 'w*', markersize=14, markeredgecolor='black', markeredgewidth=1.5)
    axes[1].text(
        town_c + 8, town_r, "Syabru Besi\n(85.343°E, 28.161°N)",
        color="white", fontsize=11, fontweight="bold",
        bbox=dict(boxstyle="round,pad=0.25", facecolor="black", alpha=0.7, edgecolor="none")
    )

    zoom_aff_km2 = np.sum(sub_aff) * 0.0001
    zoom_wat_km2 = np.sum(sub_wat) * 0.0001

    axes[1].set_title(
        f"Syabru Besi 4x4 km Zoom (Rows {r1}:{r2}, Cols {c1}:{c2})\n"
        f"Sentinel-2 Post True Colour + Affected Class Outline (red)",
        fontsize=13, fontweight="bold"
    )
    axes[1].axis("off")

    zoom_legend = [
        Line2D([0], [0], color='#ff2200', lw=2.5, label=f"Class 2: Affected Outline ({zoom_aff_km2:.3f} km²)"),
        Line2D([0], [0], color='#00c0ff', lw=2.0, label=f"Class 1: Permanent Water ({zoom_wat_km2:.3f} km²)"),
        Line2D([0], [0], marker='*', color='w', markeredgecolor='black', markersize=12, label="Town Center", linestyle="None")
    ]
    axes[1].legend(handles=zoom_legend, loc="lower left", framealpha=0.9, fontsize=11)

    fig.suptitle(
        "Layer 2 Final Hazard Detection: Sentinel-2 Optical Primary + Sentinel-1 SAR Fallback",
        fontsize=16, fontweight="bold", y=1.02
    )

    plt.savefig(output_png_path, dpi=200, bbox_inches="tight")
    plt.close(fig)

    # Also render standalone zoom image
    zoom_only_path = output_png_path.replace("quicklook_layer2.png", "quicklook_syabrubesi.png")
    if zoom_only_path != output_png_path:
        fig_z, ax_z = plt.subplots(figsize=(10, 10), constrained_layout=True)
        if post_vis is not None:
            ax_z.imshow(sub_vis)
        else:
            ax_z.imshow(post_vv[r1:r2, c1:c2], cmap="gray", vmin=-25.0, vmax=5.0)

        if np.sum(sub_aff) > 0:
            ax_z.contour(sub_aff, levels=[0.5], colors=['#ff2200'], linewidths=2.2)
            ax_z.imshow(aff_rgba)
        if np.sum(sub_wat) > 0:
            ax_z.contour(sub_wat, levels=[0.5], colors=['#00c0ff'], linewidths=1.8)
            ax_z.imshow(wat_rgba)

        ax_z.plot(town_c, town_r, 'w*', markersize=14, markeredgecolor='black', markeredgewidth=1.5)
        ax_z.text(
            town_c + 8, town_r, "Syabru Besi\n(85.343°E, 28.161°N)",
            color="white", fontsize=11, fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.25", facecolor="black", alpha=0.7, edgecolor="none")
        )
        ax_z.set_title(
            "Layer 2 Detection: Syabru Besi 4x4 km Zoom\nSentinel-2 Post True Colour (2026-08-27) + Affected Outline",
            fontsize=13, fontweight="bold", pad=10
        )
        ax_z.axis("off")
        ax_z.legend(handles=zoom_legend, loc="lower left", framealpha=0.9, fontsize=11)
        plt.savefig(zoom_only_path, dpi=200, bbox_inches="tight")
        plt.close(fig_z)

    return output_png_path

