"""
Layer 5 Quicklook Visualization Generator.
Produces:
1. Overview map of study area showing network status, settlements (cut off vs connected clear vs unverified),
   broken infrastructure elements, and target destinations.
2. High-resolution zoom plots for the 3 largest cut-off settlements showing pre-event route (green)
   and broken infrastructure elements (red).
3. Zoom map of Settlement #3's post-event connected road component (amber) illustrating why western roads
   dead-end in mountain valleys with 0 reachable destinations.
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
import networkx as nx
from scipy.spatial import cKDTree

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
    bbox: List[float],
    utm_crs: Optional[str] = None
) -> str:
    """
    Renders full study bbox overview of settlement isolation and road network status
    with 3-value status classification.
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_png_path)), exist_ok=True)

    if utm_crs is None or utm_crs == "auto":
        from src.common.crs_utils import auto_utm_crs
        utm_crs = auto_utm_crs(bbox)

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
    r_box = r_graded.cx[xmin:xmax, ymin:ymax] if len(r_graded) > 0 else r_graded
    if len(r_box) > 0 and "damage_grade" in r_box.columns:
        r_dest = r_box[r_box["damage_grade"].isin(["Destroyed", "Flooded / impassable"])]
        r_poss = r_box[r_box["damage_grade"].isin(["Possibly damaged", "Possibly flooded"])]
        r_clear = r_box[r_box["damage_grade"].isin(["Not affected", "Unknown (cloud)"])]

        if len(r_clear) > 0:
            r_clear.plot(ax=ax, color="#777777", linewidth=0.9, alpha=0.5, zorder=3)
        if len(r_poss) > 0:
            r_poss.plot(ax=ax, color="#ff9900", linewidth=2.0, linestyle="--", zorder=5)
        if len(r_dest) > 0:
            r_dest.plot(ax=ax, color="#ff0033", linewidth=2.8, zorder=6)

    # 4. Bridges
    br_box = br_graded.cx[xmin:xmax, ymin:ymax] if len(br_graded) > 0 else br_graded
    if len(br_box) > 0 and "damage_grade" in br_box.columns:
        br_dest = br_box[br_box["damage_grade"].isin(["Destroyed", "Flooded / impassable"])]
        br_poss = br_box[br_box["damage_grade"].isin(["Possibly damaged", "Possibly flooded"])]

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

    # 6. Settlements Classified by 3-Value Status
    s_view = settle_utm.cx[xmin:xmax, ymin:ymax]
    s_cutoff = s_view[s_view["vehicle_status_opt"] == "cut_off"]
    s_conn_clear = s_view[s_view["vehicle_status_opt"] == "connected (route verified clear)"]
    s_conn_unverified = s_view[s_view["vehicle_status_opt"] == "connected (unverified: route passes cloud-covered segments)"]
    s_noacc = s_view[s_view["vehicle_status_opt"].isin(["no_network_access", "isolated_pre_event"])]

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
    if len(s_conn_unverified) > 0:
        s_conn_unverified.plot(
            ax=ax,
            color="#ffcc00",
            marker="o",
            markersize=60,
            edgecolor="black",
            linewidth=1.0,
            zorder=10
        )
    if len(s_conn_clear) > 0:
        s_conn_clear.plot(
            ax=ax,
            color="#00ff66",
            marker="o",
            markersize=60,
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
        f"Layer 5 Routing & Settlement Isolation Overview\n"
        f"Vehicle: {len(s_cutoff)} Cut Off | {len(s_conn_clear)} Connected (Verified Clear) | {len(s_conn_unverified)} Connected (Cloud-Unverified) | {len(s_noacc)} No Vehicle Access",
        fontsize=12,
        fontweight="bold",
        pad=12
    )

    legend_elements = [
        Line2D([0], [0], marker="o", color="w", markerfacecolor="#ff1133", markersize=10, label=f"Cut Off ({len(s_cutoff)})"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor="#ffcc00", markersize=9, label=f"Connected (Unverified: cloud) ({len(s_conn_unverified)})"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor="#00ff66", markersize=9, label=f"Connected (Verified Clear) ({len(s_conn_clear)})"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor="#888888", markersize=7, label=f"No Pre-Event Vehicle Access ({len(s_noacc)})"),
        Line2D([0], [0], color="#ff0033", lw=3.0, label="Destroyed Road / Bridge"),
        Line2D([0], [0], color="#ff9900", lw=2.0, linestyle="--", label="Possibly Damaged Road / Bridge"),
        Line2D([0], [0], color="#777777", lw=1.2, label="Intact Road Network"),
        Line2D([0], [0], marker="P", color="w", markerfacecolor="#00ffff", markeredgecolor="black", markersize=10, label=f"Destination ({len(dest_utm)})"),
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
    all_roads_gdf: Optional[gpd.GeoDataFrame] = None,
    utm_crs: Optional[str] = None
) -> str:
    """
    Renders high-resolution zoom plot for a cut-off settlement showing pre-event route
    and all broken infrastructure elements.
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_png_path)), exist_ok=True)

    if utm_crs is None or utm_crs == "auto":
        from src.common.crs_utils import auto_utm_crs
        if all_roads_gdf is not None and len(all_roads_gdf) > 0 and all_roads_gdf.crs:
            utm_crs = auto_utm_crs(all_roads_gdf.to_crs("EPSG:4326").total_bounds)
        else:
            path_coords = settlement_dict.get("pre_path", [])
            if path_coords and len(path_coords) >= 2:
                utm_crs = auto_utm_crs(LineString(path_coords).bounds)
            else:
                raise ValueError("utm_crs must be provided when no roads or route available.")

    name = clean_label(settlement_dict["name"])
    bldgs = settlement_dict["building_count"]
    pre_len_km = settlement_dict["pre_route_km"]
    path_coords = settlement_dict["pre_path"]
    breaks = settlement_dict.get("breaks", [])
    if not breaks and "broken_element" in settlement_dict and settlement_dict["broken_element"]:
        breaks = [settlement_dict["broken_element"]]
    broken = breaks[0] if breaks else {}

    if not path_coords or len(path_coords) < 2:
        return ""

    route_line = LineString(path_coords)

    # Calculate spatial extent covering settlement and all broken elements
    xs = [p[0] for p in path_coords]
    ys = [p[1] for p in path_coords]
    for b_item in breaks:
        b_coords = b_item.get("coords")
        if b_coords:
            xs.extend([b_coords[0][0], b_coords[1][0]])
            ys.extend([b_coords[0][1], b_coords[1][1]])

    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    # Add context margin (at least 600m)
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

    # 5. Broken Infrastructure Elements (Red)
    if breaks:
        for b_item in breaks:
            b_coords = b_item.get("coords")
            if b_coords:
                b_line = LineString(b_coords)
                b_gdf = gpd.GeoDataFrame([{"geometry": b_line}], crs=utm_crs)
                b_gdf.plot(
                    ax=ax,
                    color="#ff0033",
                    linewidth=6.0,
                    zorder=15
                )

        # Primary break annotation
        if broken.get("coords"):
            b_coords = broken["coords"]
            mid_x = (b_coords[0][0] + b_coords[1][0]) / 2.0
            mid_y = (b_coords[0][1] + b_coords[1][1]) / 2.0
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

    # 7. Destination
    dest_x, dest_y = path_coords[-1]
    ax.scatter(
        [dest_x], [dest_y],
        color="#00ffff",
        s=160,
        marker="P",
        edgecolor="black",
        linewidth=1.2,
        zorder=16
    )
    ax.annotate(
        "Destination:\nHealth Facility",
        xy=(dest_x, dest_y),
        xytext=(12, 10),
        textcoords="offset points",
        fontsize=9,
        fontweight="bold",
        color="#00ffff",
        bbox=dict(boxstyle="round,pad=0.3", facecolor="black", alpha=0.85, edgecolor="#00ffff", lw=1.2),
        zorder=18
    )

    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)
    ax.set_aspect("equal")
    ax.set_title(
        f"Cut-Off Settlement #{rank}: {name} ({bldgs} buildings)\n"
        f"Pre-Event Route: {pre_len_km:.2f} km to Hospital | Breaks: {len(breaks)} destroyed elements",
        fontsize=12,
        fontweight="bold",
        pad=10
    )

    legend_elements = [
        Line2D([0], [0], marker="*", color="w", markerfacecolor="#ffff00", markeredgecolor="black", markersize=14, label=f"Origin: {name}"),
        Line2D([0], [0], color="#00ff66", lw=3.5, label=f"Pre-Event Route ({pre_len_km:.2f} km)"),
        Line2D([0], [0], color="#ff0033", lw=5.0, label=f"Destroyed Elements ({len(breaks)} cuts)"),
        Line2D([0], [0], marker="P", color="w", markerfacecolor="#00ffff", markeredgecolor="black", markersize=12, label="Destination (Health Facility)"),
        Line2D([0], [0], color="#00e5ff", lw=1.5, label="OSM waterway=river (Alignment Check)"),
        Line2D([0], [0], color="#555555", lw=1.0, label="Other Roads")
    ]
    ax.legend(handles=legend_elements, loc="upper right", framealpha=0.9, facecolor="#222222", edgecolor="#555555", fontsize=9, labelcolor="white")

    plt.tight_layout()
    plt.savefig(output_png_path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    return output_png_path


def render_settlement3_component(
    settlements_gdf: gpd.GeoDataFrame,
    G_vehicle: nx.Graph,
    output_png_path: str,
    s2_post_visual: np.ndarray,
    transform_matrix: Any,
    all_roads_gdf: Optional[gpd.GeoDataFrame] = None,
    utm_crs: Optional[str] = None
) -> str:
    """
    Renders the POST-event connected road component for Settlement #3 (near Bhrajam / cluster_29).
    Illustrates why the extensive western road network cannot reach any hospital or town destination.
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_png_path)), exist_ok=True)

    if utm_crs is None or utm_crs == "auto":
        from src.common.crs_utils import auto_utm_crs
        if settlements_gdf is not None and len(settlements_gdf) > 0 and settlements_gdf.crs:
            utm_crs = auto_utm_crs(settlements_gdf.to_crs("EPSG:4326").total_bounds)
        else:
            raise ValueError("utm_crs must be provided when settlements_gdf is empty.")

    # 1. Locate Settlement #3 (near Bhrajam)
    s3_matches = settlements_gdf[settlements_gdf["name"].str.contains("Bhrajam|भ्रजम", na=False)]
    if len(s3_matches) == 0:
        logger.info("Settlement near Bhrajam not in current study area; skipping zoom plot.")
        return ""
    s3_row = s3_matches.iloc[0]
    s3_pt = s3_row.geometry

    # 2. Extract Connected Component in G_opt
    nodes_list = list(G_vehicle.nodes)
    nodes_tree = cKDTree(np.array(nodes_list))
    d_snap, n_idx = nodes_tree.query([s3_pt.x, s3_pt.y])
    s3_node = nodes_list[n_idx]

    G_opt = G_vehicle.copy()
    for u, v, d in list(G_opt.edges(data=True)):
        if d.get("damage_grade") == "Destroyed":
            G_opt.remove_edge(u, v)

    comp = nx.node_connected_component(G_opt, s3_node)
    subG = G_opt.subgraph(comp)

    # Component edges to GeoDataFrame
    comp_lines = [LineString([u, v]) for u, v, _ in subG.edges(data=True)]
    comp_gdf = gpd.GeoDataFrame(geometry=comp_lines, crs=utm_crs)
    min_x, min_y, max_x, max_y = comp_gdf.total_bounds

    pad = 1200.0
    xmin, xmax = min_x - pad, max_x + pad
    ymin, ymax = min_y - pad, max_y + pad

    fig, ax = plt.subplots(figsize=(14, 12), dpi=200)

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

    # 2. OSM river alignment line
    draw_osm_river_centreline(
        ax,
        target_crs=utm_crs,
        clip_bounds=(xmin, ymin, xmax, ymax),
        color="#00e5ff",
        lw=1.5,
        alpha=0.9,
        zorder=12
    )

    # 3. Surrounding context roads
    if all_roads_gdf is not None and len(all_roads_gdf) > 0:
        r_crop = all_roads_gdf.cx[xmin:xmax, ymin:ymax]
        if len(r_crop) > 0:
            r_crop.plot(ax=ax, color="#555555", linewidth=1.0, alpha=0.4, zorder=3)

    # 4. Connected Road Component (Amber / Bright Yellow)
    comp_gdf.plot(
        ax=ax,
        color="#ffcc00",
        linewidth=2.2,
        alpha=0.9,
        zorder=8
    )

    # 5. Severed Break Point at way/1266396385
    dest_lines = []
    for u, v, d in G_vehicle.edges(data=True):
        if d.get("damage_grade") == "Destroyed" and d.get("osm_id") == "way/1266396385":
            dest_lines.append(LineString([u, v]))
    if dest_lines:
        dest_gdf = gpd.GeoDataFrame(geometry=dest_lines, crs=utm_crs)
        dest_gdf.plot(ax=ax, color="#ff0033", linewidth=6.0, zorder=16)
        brk_pt = dest_lines[0].centroid
        ax.annotate(
            "SEVERED: way/1266396385\n(Bottleneck to Destination)",
            xy=(brk_pt.x, brk_pt.y),
            xytext=(-80, 40),
            textcoords="offset points",
            fontsize=9.5,
            fontweight="bold",
            color="#ff3333",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="black", alpha=0.9, edgecolor="#ff0033", lw=1.5),
            arrowprops=dict(arrowstyle="->", color="#ff0033", lw=2.0),
            zorder=20
        )

    # 6. Settlement #3 Origin marker
    ax.scatter(
        [s3_pt.x], [s3_pt.y],
        color="#00ff66",
        s=200,
        marker="*",
        edgecolor="black",
        linewidth=1.5,
        zorder=18
    )
    ax.annotate(
        f"Settlement #3: {clean_label(s3_row['name'])}\n({s3_row['building_count']} buildings)",
        xy=(s3_pt.x, s3_pt.y),
        xytext=(15, -20),
        textcoords="offset points",
        fontsize=9,
        fontweight="bold",
        color="#00ff66",
        bbox=dict(boxstyle="round,pad=0.3", facecolor="black", alpha=0.85, edgecolor="#00ff66", lw=1.2),
        zorder=20
    )

    # 7. Explanatory Callout Box
    explanation = (
        "Western Road Network Isolation Analysis:\n"
        "• Road edges connect Settlement #3 westward through alpine valleys\n"
        "• Network branches terminate in alpine dead-ends\n"
        "• ZERO hospitals or health facilities exist in this western mountain enclave\n"
        "• Access to destination requires travelling through the main valley corridor,\n"
        "  which is completely severed at destroyed way/1266396385"
    )
    ax.text(
        0.02, 0.98, explanation,
        transform=ax.transAxes,
        fontsize=9.5,
        fontweight="bold",
        verticalalignment="top",
        color="#ffffff",
        bbox=dict(boxstyle="round,pad=0.5", facecolor="#1a1a1a", alpha=0.92, edgecolor="#ffcc00", lw=1.5),
        zorder=25
    )

    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)
    ax.set_aspect("equal")
    ax.set_title(
        f"Settlement #3 (near Bhrajam): Post-Event Connected Road Component\n"
        f"Reachable Subnetwork: {len(comp)} Nodes, {subG.number_of_edges()} Edges | Reachable Destinations: 0",
        fontsize=12,
        fontweight="bold",
        pad=10
    )

    legend_elements = [
        Line2D([0], [0], marker="*", color="w", markerfacecolor="#00ff66", markeredgecolor="black", markersize=14, label=f"Settlement #3 Origin ({clean_label(s3_row['name'])})"),
        Line2D([0], [0], color="#ffcc00", lw=3.0, label=f"Post-Event Connected Roads ({subG.number_of_edges()} edges)"),
        Line2D([0], [0], color="#ff0033", lw=5.0, label="Severed Bottleneck (way/1266396385)"),
        Line2D([0], [0], color="#00e5ff", lw=1.5, label="OSM waterway=river (Alignment Check)"),
        Line2D([0], [0], color="#555555", lw=1.0, label="Other Study Area Roads")
    ]
    ax.legend(handles=legend_elements, loc="lower right", framealpha=0.9, facecolor="#222222", edgecolor="#555555", fontsize=9, labelcolor="white")

    plt.tight_layout()
    plt.savefig(output_png_path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    return output_png_path


def render_dead_end_zoom(
    output_png_path: str,
    s2_post_visual: np.ndarray,
    transform_matrix: Any,
    roads_path: str = "data/raw/osm_buffered/osm_roads.geojson",
    cx: float = 332650.0,
    cy: float = 3113950.0,
    pad: float = 350.0,
    utm_crs: Optional[str] = None
) -> str:
    """
    Renders high-resolution zoom of the dead end near (332700, 3113900)
    showing all OSM ways coloured by highway type with S2 optical background.
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_png_path)), exist_ok=True)

    roads = gpd.read_file(roads_path)
    if utm_crs is None or utm_crs == "auto":
        from src.common.crs_utils import auto_utm_crs
        if len(roads) > 0 and roads.crs:
            utm_crs = auto_utm_crs(roads.to_crs("EPSG:4326").total_bounds)
        else:
            raise ValueError("utm_crs must be provided when roads are empty.")

    xmin, xmax = cx - pad, cx + pad
    roads = roads.to_crs(utm_crs)
    r_crop = roads.cx[xmin:xmax, ymin:ymax].copy()

    fig, ax = plt.subplots(figsize=(10, 10), dpi=200)

    if s2_post_visual is not None and transform_matrix is not None:
        plot_raster_background(ax, s2_post_visual, transform=transform_matrix, clip_extent=(xmin, xmax, ymin, ymax), zorder=1)
    else:
        ax.set_facecolor("#1a1a1a")
        ax.set_xlim(xmin, xmax)
        ax.set_ylim(ymin, ymax)

    draw_osm_river_centreline(ax, target_crs=utm_crs, clip_bounds=(xmin, ymin, xmax, ymax), color="#00e5ff", lw=1.5, alpha=0.9, zorder=12)

    color_map = {
        "unclassified": "#00ffcc",
        "construction": "#ff00aa",
        "path": "#ffcc00",
        "track": "#ff9900",
        "footway": "#ffff66"
    }

    for hwy, group in r_crop.groupby("highway"):
        col = color_map.get(str(hwy), "#ffffff")
        ls = "--" if hwy in ["path", "construction", "footway"] else "-"
        lw = 3.5 if hwy in ["unclassified", "construction"] else 2.0
        group.plot(ax=ax, color=col, linewidth=lw, linestyle=ls, zorder=8, alpha=0.9)

    ax.scatter([332608.3], [3114099.2], color="#00ffcc", s=140, edgecolor="black", linewidth=1.5, zorder=15)
    ax.annotate(
        "Dead End: way/853752343 (unclassified)\nContinues only as path (way/341804931)",
        xy=(332608.3, 3114099.2),
        xytext=(-60, 25),
        textcoords="offset points",
        fontsize=8.5,
        fontweight="bold",
        color="#00ffcc",
        bbox=dict(boxstyle="round,pad=0.3", facecolor="black", alpha=0.85, edgecolor="#00ffcc", lw=1.2),
        arrowprops=dict(arrowstyle="->", color="#00ffcc", lw=1.5),
        zorder=20
    )

    ax.scatter([332722.3], [3113938.5], color="#ff00aa", s=140, edgecolor="black", linewidth=1.5, zorder=15)
    ax.annotate(
        "Shared Node: (332722, 3113938)\nway/341811083 (construction: unclassified)\n[Excluded from vehicle network]",
        xy=(332722.3, 3113938.5),
        xytext=(20, -35),
        textcoords="offset points",
        fontsize=8.5,
        fontweight="bold",
        color="#ff00aa",
        bbox=dict(boxstyle="round,pad=0.3", facecolor="black", alpha=0.85, edgecolor="#ff00aa", lw=1.2),
        arrowprops=dict(arrowstyle="->", color="#ff00aa", lw=1.5),
        zorder=20
    )

    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)
    ax.set_aspect("equal")
    ax.set_title(
        "Topology Gap Zoom: Dead End near (332700, 3113900)\nExcluded Highway Types (construction & path) Sever Network Continuation",
        fontsize=11,
        fontweight="bold",
        pad=10
    )

    handles = [
        Line2D([0], [0], color="#00ffcc", lw=3.5, label="unclassified (way/853752343, in vehicle net)"),
        Line2D([0], [0], color="#ff00aa", lw=3.5, linestyle="--", label="construction (way/341811083, excluded)"),
        Line2D([0], [0], color="#ffcc00", lw=2.0, linestyle="--", label="path (way/341804931, etc., excluded)"),
        Line2D([0], [0], color="#00e5ff", lw=1.5, label="OSM waterway=river (Alignment Check)")
    ]
    ax.legend(handles=handles, loc="upper left", framealpha=0.9, facecolor="#222222", edgecolor="#555555", fontsize=8.5, labelcolor="white")

    plt.tight_layout()
    plt.savefig(output_png_path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    return output_png_path
