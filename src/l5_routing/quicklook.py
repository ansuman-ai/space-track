"""
Layer 5 Quicklook Visualization Generator.
Produces:
1. Overview map of study area showing network status, settlements (cut off vs connected),
   broken infrastructure elements, and target destinations.
2. High-resolution zoom plots for the 3 largest cut-off settlements showing pre-event route (green)
   and broken infrastructure element (red).
Strictly uses plot_utils for georeferenced raster background and river alignment line.
"""

import os
os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import numpy as np
import warnings
warnings.filterwarnings("ignore", category=UserWarning)
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
import geopandas as gpd
from shapely.geometry import Point, LineString, box

from src.common.plot_utils import (
    plot_raster_background,
    reproject_vector,
    draw_osm_river_centreline,
)

NEPALI_TRANSLITERATION = {
    "आमाछोदिङ्मो": "Amachhodingmo",
    "बाहुनडाँडा": "Bahundanda",
    "लिङलिङ": "Lingling",
    "डाल्फेडी": "Dalphedi",
    "शेर्पागाउँ": "Sherpagaun",
    "दुर्सागाङ": "Dursagang",
    "भञ्ज्याङ": "Bhanjyang",
    "ठुलो": "Thulo",
    "भार्खु": "Bharkhu",
    "पाजुङ": "Pajung",
    "नागथली": "Nagathali",
    "तिवारी": "Tiwari",
    "ब्राबल": "Brabal",
    "खाङजिम": "Khangjim",
    "सानाे": "Sano",
    "स्याप्रु": "Syaphru",
    "भ्रजम": "Bhrajam",
    "चंदन": "Chandan",
    "ब्रिमडाङ": "Brimdang",
    "पैरो": "Pairo",
    "चोलाङपाटी": "Cholangpati",
    "डोमेन": "Domen",
    "सुर्का": "Surka",
    "बाडी": "Badi",
    "स्वास्थ्य चौकी": "Health Post",
    "बालकुमारी स्वास्थ्य चौकी": "Balkumari Health Post",
    "शिखरबेंसी गाउँघर क्लिनिक": "Shikharbesi Clinic",
    "शिखरबेंसी स्वास्थ्य चौकी": "Shikharbesi Health Post",
}

def clean_label(text: Any) -> str:
    s = str(text)
    for k, v in NEPALI_TRANSLITERATION.items():
        s = s.replace(k, v)
    return s


def render_l5_overview(
    settlements_gdf: gpd.GeoDataFrame,
    destinations_gdf: gpd.GeoDataFrame,
    roads_graded_path: str,
    bridges_graded_path: str,
    output_png_path: str,
    s2_post_visual: np.ndarray,
    transform_matrix: Any,
    bbox: List[float] = [85.30, 28.10, 85.42, 28.25],
    utm_crs: str = "EPSG:32645"
) -> str:
    """
    Renders full study bbox overview of settlement isolation and road network status.
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_png_path)), exist_ok=True)

    r_graded = gpd.read_file(roads_graded_path).to_crs(utm_crs)
    br_graded = gpd.read_file(bridges_graded_path).to_crs(utm_crs)
    dest_utm = reproject_vector(destinations_gdf, utm_crs)
    settle_utm = reproject_vector(settlements_gdf, utm_crs)

    # Compute bounding box in UTM
    bbox_poly = gpd.GeoSeries([box(*bbox)], crs="EPSG:4326").to_crs(utm_crs).iloc[0]
    xmin, ymin, xmax, ymax = bbox_poly.bounds
    pad = 500.0
    xmin, xmax = xmin - pad, xmax + pad
    ymin, ymax = ymin - pad, ymax + pad

    fig, ax = plt.subplots(figsize=(14, 16), dpi=200)

    # 1. Raster Background
    if s2_post_visual is not None and transform_matrix is not None:
        plot_raster_background(
            ax,
            s2_post_visual,
            transform=transform_matrix,
            clip_extent=(xmin, xmax, ymin, ymax),
            zorder=1
        )
    else:
        ax.set_facecolor("#151515")
        ax.set_xlim(xmin, xmax)
        ax.set_ylim(ymin, ymax)

    # 2. OSM waterway=river Alignment Line
    draw_osm_river_centreline(
        ax,
        target_crs=utm_crs,
        clip_bounds=(xmin, ymin, xmax, ymax),
        color="#00e5ff",
        lw=1.5,
        alpha=0.9,
        zorder=12
    )

    # 3. Road Network
    r_box = r_graded.cx[xmin:xmax, ymin:ymax]
    r_dest = r_box[r_box["damage_grade"] == "Destroyed"]
    r_poss = r_box[r_box["damage_grade"] == "Possibly damaged"]
    r_clear = r_box[r_box["damage_grade"].isin(["Not affected", "Unknown (cloud)"])]

    if len(r_clear) > 0:
        r_clear.plot(ax=ax, color="#777777", linewidth=0.9, alpha=0.5, zorder=3)
    if len(r_poss) > 0:
        r_poss.plot(ax=ax, color="#ff9900", linewidth=2.0, linestyle="--", zorder=5)
    if len(r_dest) > 0:
        r_dest.plot(ax=ax, color="#ff0033", linewidth=2.8, zorder=6)

    # 4. Bridges
    br_box = br_graded.cx[xmin:xmax, ymin:ymax]
    br_dest = br_box[br_box["damage_grade"] == "Destroyed"]
    br_poss = br_box[br_box["damage_grade"] == "Possibly damaged"]

    if len(br_poss) > 0:
        br_poss.plot(ax=ax, color="#ff9900", linewidth=3.5, zorder=7)
    if len(br_dest) > 0:
        br_dest.plot(ax=ax, color="#ff0033", linewidth=4.5, zorder=8)

    # 5. Target Destinations inside/near view
    d_view = dest_utm.cx[xmin:xmax, ymin:ymax]
    if len(d_view) > 0:
        d_view.plot(
            ax=ax,
            color="#00ffff",
            marker="P",
            markersize=130,
            edgecolor="black",
            linewidth=1.2,
            zorder=14
        )
        for _, d_row in d_view.iterrows():
            ax.annotate(
                clean_label(d_row["name"]),
                xy=(d_row.geometry.x, d_row.geometry.y),
                xytext=(8, 8),
                textcoords="offset points",
                fontsize=8,
                fontweight="bold",
                color="#00ffff",
                bbox=dict(boxstyle="round,pad=0.2", facecolor="black", alpha=0.7, edgecolor="#00ffff", lw=0.8),
                zorder=15
            )

    # 6. Settlements
    s_view = settle_utm.cx[xmin:xmax, ymin:ymax]
    s_cutoff = s_view[s_view["vehicle_status_opt"] == "cut_off"]
    s_conn = s_view[s_view["vehicle_status_opt"] == "connected"]
    s_noacc = s_view[s_view["vehicle_status_opt"] == "no_network_access"]

    if len(s_noacc) > 0:
        s_noacc.plot(
            ax=ax,
            color="#888888",
            marker="o",
            markersize=35,
            edgecolor="#333333",
            linewidth=0.8,
            alpha=0.7,
            zorder=9
        )
    if len(s_conn) > 0:
        s_conn.plot(
            ax=ax,
            color="#00ff66",
            marker="o",
            markersize=55,
            edgecolor="black",
            linewidth=1.0,
            zorder=10
        )
    if len(s_cutoff) > 0:
        s_cutoff.plot(
            ax=ax,
            color="#ff1133",
            marker="o",
            markersize=80,
            edgecolor="white",
            linewidth=1.2,
            zorder=11
        )

        # Annotate top 5 cut-off settlements
        top_cut = s_cutoff.sort_values(by="building_count", ascending=False).head(5)
        for _, c_row in top_cut.iterrows():
            ax.annotate(
                f"{clean_label(c_row['name'])} ({c_row['building_count']} bldgs)",
                xy=(c_row.geometry.x, c_row.geometry.y),
                xytext=(10, -5),
                textcoords="offset points",
                fontsize=8,
                fontweight="bold",
                color="#ffcccc",
                bbox=dict(boxstyle="round,pad=0.25", facecolor="#440000", alpha=0.85, edgecolor="#ff3333", lw=1.0),
                zorder=16
            )

    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)
    ax.set_aspect("equal")
    ax.set_title(
        f"Layer 5 Routing & Settlement Isolation Overview (Trishuli / Syabru Besi)\n"
        f"Settlements: {len(s_cutoff)} Cut Off (Vehicle) | {len(s_conn)} Connected | {len(s_noacc)} No Vehicle Access",
        fontsize=13,
        fontweight="bold",
        pad=12
    )

    legend_elements = [
        Line2D([0], [0], marker="o", color="w", markerfacecolor="#ff1133", markersize=10, label=f"Settlement Cut Off ({len(s_cutoff)})"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor="#00ff66", markersize=9, label=f"Settlement Connected ({len(s_conn)})"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor="#888888", markersize=7, label=f"No Vehicle Access ({len(s_noacc)})"),
        Line2D([0], [0], color="#ff0033", lw=3.0, label="Destroyed Road / Bridge"),
        Line2D([0], [0], color="#ff9900", lw=2.0, linestyle="--", label="Possibly Damaged Road / Bridge"),
        Line2D([0], [0], color="#777777", lw=1.2, label="Intact Road Network"),
        Line2D([0], [0], marker="P", color="w", markerfacecolor="#00ffff", markeredgecolor="black", markersize=10, label=f"Health Facility Destination ({len(dest_utm)})"),
        Line2D([0], [0], color="#00e5ff", lw=1.5, label="OSM waterway=river (Alignment Check)")
    ]
    ax.legend(handles=legend_elements, loc="lower right", framealpha=0.9, facecolor="#222222", edgecolor="#555555", fontsize=9, labelcolor="white")

    plt.tight_layout()
    plt.savefig(output_png_path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    return output_png_path


def render_cutoff_zoom(
    settlement_dict: Dict[str, Any],
    rank: int,
    output_png_path: str,
    s2_post_visual: np.ndarray,
    transform_matrix: Any,
    all_roads_gdf: gpd.GeoDataFrame,
    utm_crs: str = "EPSG:32645"
) -> str:
    """
    Renders a dedicated zoom plot for a cut-off settlement showing:
    - Pre-event route in vibrant green (#00ff66)
    - Severed infrastructure element in bold red (#ff0033)
    - High-resolution optical background and river alignment line
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_png_path)), exist_ok=True)

    name = clean_label(settlement_dict["name"])
    bldgs = settlement_dict["building_count"]
    pre_len_km = settlement_dict["pre_route_km"]
    path_coords = settlement_dict["pre_path"]
    broken = settlement_dict.get("broken_element", {})

    if not path_coords or len(path_coords) < 2:
        return ""

    route_line = LineString(path_coords)
    broken_coords = broken.get("coords") if broken else None

    # Calculate spatial extent covering settlement and broken element
    xs = [p[0] for p in path_coords]
    ys = [p[1] for p in path_coords]
    if broken_coords:
        xs.extend([broken_coords[0][0], broken_coords[1][0]])
        ys.extend([broken_coords[0][1], broken_coords[1][1]])

    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    # Add context margin (at least 500m)
    margin = max(600.0, 0.15 * max(max_x - min_x, max_y - min_y))
    xmin, xmax = min_x - margin, max_x + margin
    ymin, ymax = min_y - margin, max_y + margin

    fig, ax = plt.subplots(figsize=(12, 12), dpi=200)

    # 1. Raster Background
    if s2_post_visual is not None and transform_matrix is not None:
        plot_raster_background(
            ax,
            s2_post_visual,
            transform=transform_matrix,
            clip_extent=(xmin, xmax, ymin, ymax),
            zorder=1
        )
    else:
        ax.set_facecolor("#151515")
        ax.set_xlim(xmin, xmax)
        ax.set_ylim(ymin, ymax)

    # 2. River Alignment Line
    draw_osm_river_centreline(
        ax,
        target_crs=utm_crs,
        clip_bounds=(xmin, ymin, xmax, ymax),
        color="#00e5ff",
        lw=1.5,
        alpha=0.9,
        zorder=12
    )

    # 3. Context Road Network
    if all_roads_gdf is not None and len(all_roads_gdf) > 0:
        r_crop = all_roads_gdf.cx[xmin:xmax, ymin:ymax]
        if len(r_crop) > 0:
            r_crop.plot(ax=ax, color="#555555", linewidth=1.0, alpha=0.5, zorder=3)

    # 4. Pre-event Route (Green)
    route_gdf = gpd.GeoDataFrame([{"geometry": route_line}], crs=utm_crs)
    route_gdf.plot(
        ax=ax,
        color="#00ff66",
        linewidth=3.5,
        alpha=0.9,
        zorder=10
    )

    # 5. Broken Infrastructure Element (Red)
    if broken_coords:
        broken_line = LineString(broken_coords)
        brk_gdf = gpd.GeoDataFrame([{"geometry": broken_line}], crs=utm_crs)
        brk_gdf.plot(
            ax=ax,
            color="#ff0033",
            linewidth=6.0,
            zorder=15
        )

        mid_x = (broken_coords[0][0] + broken_coords[1][0]) / 2.0
        mid_y = (broken_coords[0][1] + broken_coords[1][1]) / 2.0
        brk_label = f"SEVERED: {broken.get('osm_id')} ({broken.get('highway')})"
        ax.annotate(
            brk_label,
            xy=(mid_x, mid_y),
            xytext=(15, 20),
            textcoords="offset points",
            fontsize=9,
            fontweight="bold",
            color="#ff3333",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="black", alpha=0.85, edgecolor="#ff0033", lw=1.2),
            arrowprops=dict(arrowstyle="->", color="#ff0033", lw=1.5),
            zorder=18
        )

    # 6. Settlement Origin
    orig_x, orig_y = path_coords[0]
    ax.scatter(
        [orig_x], [orig_y],
        color="#ffff00",
        s=180,
        marker="*",
        edgecolor="black",
        linewidth=1.2,
        zorder=16
    )
    ax.annotate(
        f"{name}\n({bldgs} buildings)",
        xy=(orig_x, orig_y),
        xytext=(12, -15),
        textcoords="offset points",
        fontsize=10,
        fontweight="bold",
        color="#ffff88",
        bbox=dict(boxstyle="round,pad=0.3", facecolor="black", alpha=0.85, edgecolor="#ffff00", lw=1.2),
        zorder=18
    )

    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)
    ax.set_aspect("equal")
    ax.set_title(
        f"Cut-Off Settlement #{rank}: {name} ({bldgs} buildings)\n"
        f"Pre-Event Route: {pre_len_km:.2f} km | Break Point: {broken.get('osm_id', 'unknown')}",
        fontsize=12,
        fontweight="bold",
        pad=10
    )

    legend_elements = [
        Line2D([0], [0], marker="*", color="w", markerfacecolor="#ffff00", markeredgecolor="black", markersize=14, label=f"Origin: {name}"),
        Line2D([0], [0], color="#00ff66", lw=3.5, label=f"Pre-Event Route ({pre_len_km:.2f} km)"),
        Line2D([0], [0], color="#ff0033", lw=5.0, label=f"Broken Element ({broken.get('osm_id', 'Severed')})"),
        Line2D([0], [0], color="#00e5ff", lw=1.5, label="OSM waterway=river (Alignment Check)"),
        Line2D([0], [0], color="#555555", lw=1.0, label="Other Roads")
    ]
    ax.legend(handles=legend_elements, loc="upper right", framealpha=0.9, facecolor="#222222", edgecolor="#555555", fontsize=9, labelcolor="white")

    plt.tight_layout()
    plt.savefig(output_png_path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    return output_png_path
