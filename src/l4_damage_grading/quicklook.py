"""
Layer 4 Quicklook Visualization Generator.
High-resolution 4x4 km zoom on Syabru Besi showcasing:
- Sentinel-2 Post True Colour optical composite background (strictly georeferenced)
- Flood hazard outlines (Class 2: Observed, Class 3: Inferred)
- Pre-event OSM river centreline for built-in visual alignment verification
- Critical infrastructure damage grades:
  - Buildings: Destroyed (red), Damaged (magenta/orange), Possibly damaged (yellow)
  - Roads: Destroyed (red solid), Possibly damaged (orange dashed)
  - Bridges: Destroyed (red diamonds), Possibly damaged (orange diamonds)
"""

import os
from typing import Dict, Any, Optional, Tuple
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import geopandas as gpd
import rasterio

from src.common.plot_utils import (
    plot_raster_background,
    reproject_vector,
    draw_osm_river_centreline,
)


def render_l4_quicklook(
    s2_post_visual: np.ndarray,
    buildings_gdf: gpd.GeoDataFrame,
    roads_gdf: gpd.GeoDataFrame,
    bridges_gdf: gpd.GeoDataFrame,
    hazard_gdf: gpd.GeoDataFrame,
    output_png_path: str,
    zoom_center_utm: Tuple[float, float] = (337320.0, 3115840.0),
    zoom_half_width_m: float = 2000.0,
    utm_crs: str = "EPSG:32645",
    transform_matrix: Any = None
) -> str:
    """
    Renders Syabru Besi 4x4 km damage grading overview map with unified alignment.
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_png_path)), exist_ok=True)

    cx, cy = zoom_center_utm
    xmin, xmax = cx - zoom_half_width_m, cx + zoom_half_width_m
    ymin, ymax = cy - zoom_half_width_m, cy + zoom_half_width_m

    if transform_matrix is None:
        ref_path = "data/processed/hazard_classes.tif"
        if os.path.exists(ref_path):
            with rasterio.open(ref_path) as src:
                transform_matrix = src.transform

    # Re-project vectors to UTM for spatial alignment with raster
    b_utm = reproject_vector(buildings_gdf, utm_crs)
    r_utm = reproject_vector(roads_gdf, utm_crs)
    br_utm = reproject_vector(bridges_gdf, utm_crs)
    haz_utm = reproject_vector(hazard_gdf, utm_crs)

    fig, ax = plt.subplots(figsize=(12, 12), dpi=200)

    # Plot georeferenced raster background
    if s2_post_visual is not None and transform_matrix is not None:
        extent, _ = plot_raster_background(
            ax,
            s2_post_visual,
            transform=transform_matrix,
            clip_extent=(xmin, xmax, ymin, ymax),
            zorder=1
        )
    else:
        ax.set_facecolor("#1a1a1a")
        extent = (xmin, xmax, ymin, ymax)
        ax.set_xlim(xmin, xmax)
        ax.set_ylim(ymin, ymax)

    # 1. Overlay Layer 2 Hazard Polygons
    if len(haz_utm) > 0:
        c3_polys = haz_utm[haz_utm["class"] == 3]
        if len(c3_polys) > 0:
            c3_clipped = c3_polys.clip_by_rect(xmin, ymin, xmax, ymax)
            c3_clipped = c3_clipped[~c3_clipped.is_empty]
            if len(c3_clipped) > 0:
                c3_clipped.plot(ax=ax, facecolor=(1.0, 0.55, 0.0, 0.25), edgecolor="#ff8800", linewidth=1.5, linestyle="--", zorder=3)

        c2_polys = haz_utm[haz_utm["class"] == 2]
        if len(c2_polys) > 0:
            c2_clipped = c2_polys.clip_by_rect(xmin, ymin, xmax, ymax)
            c2_clipped = c2_clipped[~c2_clipped.is_empty]
            if len(c2_clipped) > 0:
                c2_clipped.plot(ax=ax, facecolor=(0.95, 0.15, 0.0, 0.35), edgecolor="#ff2200", linewidth=2.0, zorder=4)

    # Built-in River Centreline Alignment Verification
    draw_osm_river_centreline(ax, target_crs=utm_crs, clip_bounds=(xmin, ymin, xmax, ymax), color="#00e5ff", lw=1.2, zorder=12)

    # 2. Roads Overlay
    if len(r_utm) > 0:
        r_box = r_utm.cx[xmin:xmax, ymin:ymax]
        r_dest = r_box[r_box["damage_grade"] == "Destroyed"]
        r_poss = r_box[r_box["damage_grade"] == "Possibly damaged"]
        r_clear = r_box[r_box["damage_grade"] == "Not affected"]

        if len(r_clear) > 0:
            r_clear.plot(ax=ax, color="#cccccc", linewidth=1.2, alpha=0.6, zorder=5)
        if len(r_poss) > 0:
            r_poss.plot(ax=ax, color="#ff8800", linewidth=2.2, linestyle="--", zorder=6)
        if len(r_dest) > 0:
            r_dest.plot(ax=ax, color="#ff0000", linewidth=2.8, zorder=7)

    # 3. Buildings Overlay
    if len(b_utm) > 0:
        b_box = b_utm.cx[xmin:xmax, ymin:ymax]
        b_dest = b_box[b_box["damage_grade"] == "Destroyed"]
        b_dmg = b_box[b_box["damage_grade"] == "Damaged"]
        b_poss = b_box[b_box["damage_grade"] == "Possibly damaged"]
        b_cloud = b_box[b_box["damage_grade"] == "Unknown (cloud)"]

        if len(b_cloud) > 0:
            b_cloud.plot(ax=ax, facecolor="#777777", edgecolor="#555555", linewidth=0.5, alpha=0.5, zorder=8)
        if len(b_poss) > 0:
            b_poss.plot(ax=ax, facecolor="#ffcc00", edgecolor="#cc9900", linewidth=1.2, alpha=0.9, zorder=9)
        if len(b_dmg) > 0:
            b_dmg.plot(ax=ax, facecolor="#ff6600", edgecolor="#b34700", linewidth=1.4, alpha=0.95, zorder=9)
        if len(b_dest) > 0:
            b_dest.plot(ax=ax, facecolor="#ff0022", edgecolor="#880011", linewidth=1.6, alpha=1.0, zorder=10)

    # 4. Bridges Overlay
    if len(br_utm) > 0:
        br_box = br_utm.cx[xmin:xmax, ymin:ymax]
        for _, br in br_box.iterrows():
            pt = br.geometry.centroid
            if br["damage_grade"] == "Destroyed":
                ax.plot(pt.x, pt.y, marker="D", color="#ff0044", markeredgecolor="white", markersize=9, markeredgewidth=1.2, zorder=11)
            elif br["damage_grade"] == "Possibly damaged":
                ax.plot(pt.x, pt.y, marker="D", color="#ff8800", markeredgecolor="white", markersize=8, markeredgewidth=1.2, zorder=11)
            else:
                ax.plot(pt.x, pt.y, marker="D", color="#00ffcc", markeredgecolor="black", markersize=6, zorder=11)

    # Town center star marker
    ax.plot(cx, cy, marker="*", color="white", markeredgecolor="black", markersize=14, markeredgewidth=1.5, zorder=15)
    ax.text(
        cx + 60, cy, "Syabru Besi\n(85.343°E, 28.161°N)",
        color="white", fontsize=10, fontweight="bold",
        bbox=dict(boxstyle="round,pad=0.25", facecolor="black", alpha=0.75, edgecolor="none"),
        zorder=15
    )

    ax.set_xlim(extent[0], extent[1])
    ax.set_ylim(extent[2], extent[3])
    ax.axis("off")

    # Legend
    legend_elements = [
        Line2D([0], [0], color="#ff2200", lw=3.0, label="Class 2 Hazard: Flood/Debris"),
        Line2D([0], [0], color="#ff8800", lw=2.5, linestyle="--", label="Class 3 Hazard: Inferred Flooded"),
        Line2D([0], [0], color="#00e5ff", lw=1.2, label="OSM River Centreline (Alignment Check)"),
        Line2D([0], [0], marker="s", color="w", markerfacecolor="#ff0022", markeredgecolor="#880011", markersize=10, label=f"Building: Destroyed ({len(b_dest) if 'b_dest' in locals() else 0})"),
        Line2D([0], [0], marker="s", color="w", markerfacecolor="#ff6600", markeredgecolor="#b34700", markersize=10, label=f"Building: Damaged ({len(b_dmg) if 'b_dmg' in locals() else 0})"),
        Line2D([0], [0], marker="s", color="w", markerfacecolor="#ffcc00", markeredgecolor="#cc9900", markersize=10, label=f"Building: Possibly Damaged ({len(b_poss) if 'b_poss' in locals() else 0})"),
        Line2D([0], [0], color="#ff0000", lw=2.5, label="Road: Destroyed"),
        Line2D([0], [0], color="#ff8800", lw=2.0, linestyle="--", label="Road: Possibly Damaged"),
        Line2D([0], [0], marker="D", color="w", markerfacecolor="#ff0044", markeredgecolor="white", markersize=9, label="Bridge: Destroyed"),
        Line2D([0], [0], marker="D", color="w", markerfacecolor="#ff8800", markeredgecolor="white", markersize=8, label="Bridge: Possibly Damaged"),
        Line2D([0], [0], marker="*", color="w", markeredgecolor="black", markersize=12, label="Syabru Besi Center", linestyle="None")
    ]
    ax.legend(handles=legend_elements, loc="lower left", framealpha=0.9, fontsize=9.5)

    ax.set_title(
        "Layer 4: Critical Infrastructure Damage Grading (Syabru Besi 4x4 km Zoom)\n"
        "Sentinel-2 Post True Colour (2026-08-27) + River Alignment Check (cyan)",
        fontsize=12, fontweight="bold", pad=12
    )

    plt.savefig(output_png_path, bbox_inches="tight")
    plt.close()

    return output_png_path
