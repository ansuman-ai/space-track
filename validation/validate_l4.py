"""
Layer 4 Validation: Copernicus EMS EMSR927 Damage Grading Comparison.
Evaluates Layer 4 infrastructure damage classifications against Copernicus EMS ground truth:
- builtUpP (433 points: 323 destroyed, 32 damaged, 78 possibly damaged)
- transportationL (31 road lines)
- transportationP (5 bridges: all destroyed)
Uses unified plot_utils with strictly georeferenced background and built-in river centreline check.
"""

import os
import sys
import shutil
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import geopandas as gpd
import numpy as np
import rasterio
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

from src.common.plot_utils import (
    plot_raster_background,
    draw_osm_river_centreline,
    reproject_vector,
)


def run_validation_l4():
    ems_dir = Path("validation/emsr927")
    out_dir = Path("validation")
    output_png = out_dir / "quicklook_validation_l4.png"
    utm_crs = "EPSG:32645"

    # 1. Load Copernicus EMS Ground Truth
    aoi_gdf = reproject_vector(gpd.read_file(ems_dir / "EMSR927_AOI01_GRA_PRODUCT_areaOfInterestA_v1.shp"), utm_crs)
    aoi_poly = aoi_gdf.union_all()

    ems_b = reproject_vector(gpd.read_file(ems_dir / "EMSR927_AOI01_GRA_PRODUCT_builtUpP_v1.shp"), utm_crs)
    ems_r = reproject_vector(gpd.read_file(ems_dir / "EMSR927_AOI01_GRA_PRODUCT_transportationL_v1.shp"), utm_crs)
    ems_br = reproject_vector(gpd.read_file(ems_dir / "EMSR927_AOI01_GRA_PRODUCT_transportationP_v1.shp"), utm_crs)
    ems_ev = reproject_vector(gpd.read_file(ems_dir / "EMSR927_AOI01_GRA_PRODUCT_observedEventA_v1.shp"), utm_crs)

    ems_r["length_km"] = ems_r.length / 1000.0

    # 2. Load Our Layer 4 Predictions
    our_b = reproject_vector(gpd.read_file("data/processed/buildings_graded.geojson"), utm_crs)
    our_r = reproject_vector(gpd.read_file("data/processed/roads_graded.geojson"), utm_crs)
    our_br = reproject_vector(gpd.read_file("data/processed/bridges_graded.geojson"), utm_crs)
    haz_gdf = reproject_vector(gpd.read_file("data/processed/hazard_polygons.geojson"), utm_crs)

    # Filter our features inside EMS AOI for apples-to-apples comparison
    our_b_aoi = our_b[our_b.intersects(aoi_poly)]
    our_r_aoi = our_r[our_r.intersects(aoi_poly)]
    our_br_aoi = our_br[our_br.intersects(aoi_poly)]

    # 3. Buildings Comparison
    ems_b_counts = ems_b["damage_gra"].value_counts().to_dict()
    our_b_aoi_counts = our_b_aoi["damage_grade"].value_counts().to_dict()
    our_b_total_counts = our_b["damage_grade"].value_counts().to_dict()

    our_b_aff = our_b[our_b["damage_grade"].isin(["Destroyed", "Damaged", "Possibly damaged"])]
    our_b_not = our_b[our_b["damage_grade"] == "Not affected"]
    our_b_unk = our_b[our_b["damage_grade"] == "Unknown (cloud)"]
    our_b_aoi_aff = our_b_aoi[our_b_aoi["damage_grade"].isin(["Destroyed", "Damaged", "Possibly damaged"])]

    geom_aff = our_b_aff.union_all()
    geom_not = our_b_not.union_all()
    geom_unk = our_b_unk.union_all()
    geom_all_osm = our_b.union_all()

    d_aff = ems_b.distance(geom_aff)
    d_not = ems_b.distance(geom_not)
    d_unk = ems_b.distance(geom_unk)
    d_all = ems_b.distance(geom_all_osm)

    ems_matched_aff_30m = int((d_aff <= 30.0).sum())
    pct_ems_matched_aff = (ems_matched_aff_30m / len(ems_b)) * 100.0

    ems_no_aff_30m = (d_aff > 30.0)
    ems_matched_not_30m = int((ems_no_aff_30m & (d_not <= 30.0)).sum())
    ems_matched_unk_30m = int((ems_no_aff_30m & (~(d_not <= 30.0)) & (d_unk <= 30.0)).sum())
    ems_no_osm_30m = int((d_all > 30.0).sum())

    # Distance from our affected buildings inside AOI to nearest EMS point
    ems_b_geom = ems_b.union_all()
    our_aff_dist_to_ems = our_b_aoi_aff.distance(ems_b_geom)
    our_aff_matched_30m = int((our_aff_dist_to_ems <= 30.0).sum())
    pct_our_aff_matched = (our_aff_matched_30m / len(our_b_aoi_aff) * 100.0) if len(our_b_aoi_aff) > 0 else 0.0

    # 4. Bridges Comparison
    ems_br_geom = ems_br.union_all()
    our_br_aff = our_br[our_br["damage_grade"].isin(["Destroyed", "Possibly damaged"])]
    our_br_aoi_aff = our_br_aoi[our_br_aoi["damage_grade"].isin(["Destroyed", "Possibly damaged"])]
    d_br_aff = ems_br.distance(our_br_aff.union_all())
    ems_br_matched_30m = int((d_br_aff <= 30.0).sum())
    pct_ems_br_matched = (ems_br_matched_30m / len(ems_br)) * 100.0

    d_our_br_to_ems = our_br_aoi_aff.distance(ems_br_geom)
    our_br_matched_30m = int((d_our_br_to_ems <= 30.0).sum())
    pct_our_br_matched = (our_br_matched_30m / len(our_br_aoi_aff) * 100.0) if len(our_br_aoi_aff) > 0 else 0.0

    # 5. Roads Comparison
    ems_r_total_km = float(ems_r.length.sum() / 1000.0)
    ems_r_buff = ems_r.buffer(30.0).union_all()
    our_r_aff = our_r[our_r["damage_grade"].isin(["Destroyed", "Possibly damaged"])]
    our_r_aoi_aff = our_r_aoi[our_r_aoi["damage_grade"].isin(["Destroyed", "Possibly damaged"])]
    our_r_aff_buff = our_r_aff.buffer(30.0).union_all()

    ems_r_matched_km = float(ems_r.intersection(our_r_aff_buff).length.sum() / 1000.0)
    our_r_aoi_aff_km = float(our_r_aoi_aff.length.sum() / 1000.0)
    our_r_matched_km = float(our_r_aoi_aff.intersection(ems_r_buff).length.sum() / 1000.0)

    print("\n==================== LAYER 4 VALIDATION REPORT ====================")
    print("1. BUILDINGS:")
    print(f"   EMS Affected Buildings (Total {len(ems_b)}):")
    print(f"     - With OSM building within 30m graded affected (any class): {ems_matched_aff_30m} ({pct_ems_matched_aff:.1f}%)")
    print(f"     - With nearest OSM building graded 'Not affected':          {ems_matched_not_30m} ({ems_matched_not_30m/len(ems_b)*100:.1f}%)")
    print(f"     - With nearest OSM building graded 'Unknown (cloud)':       {ems_matched_unk_30m} ({ems_matched_unk_30m/len(ems_b)*100:.1f}%)")
    print(f"     - With NO pre-event OSM building within 30m (omission):     {ems_no_osm_30m} ({ems_no_osm_30m/len(ems_b)*100:.1f}%)")
    print(f"   Our Affected Buildings in AOI (Total {len(our_b_aoi_aff)}):")
    print(f"     - Within 30m of an EMS affected point:                      {our_aff_matched_30m} / {len(our_b_aoi_aff)} ({pct_our_aff_matched:.1f}%)")

    print("\n2. BRIDGES:")
    print(f"   EMS Bridges (Total {len(ems_br)}, all destroyed):")
    print(f"     - With OSM bridge within 30m graded affected:               {ems_br_matched_30m} / {len(ems_br)} ({pct_ems_br_matched:.1f}%)")
    print(f"   Our Affected Bridges in AOI (Total {len(our_br_aoi_aff)}):")
    print(f"     - Within 30m of an EMS bridge:                              {our_br_matched_30m} / {len(our_br_aoi_aff)} ({pct_our_br_matched:.1f}%)")
    print(f"   Every Bridge Graded Affected (Total {len(our_br_aff)}):")
    for idx, row in our_br_aff.iterrows():
        osm_id = row.get("@osmId", "unknown")
        hwy = row.get("highway", "unknown")
        rule = row.get("rule", "none")
        dist = row.get("distance_m", 0.0)
        grade = row.get("damage_grade", "unknown")
        print(f"     - {osm_id:18s} | {hwy:12s} | {grade:16s} | rule: {rule:8s} | dist: {dist:5.1f}m")


    print("\n3. ROADS:")
    print(f"   EMS Affected Roads in AOI (Total {ems_r_total_km:.2f} km):")
    print(f"     - Within 30m of our affected roads:                         {ems_r_matched_km:.2f} km ({ems_r_matched_km/ems_r_total_km*100:.1f}%)")
    print(f"   Our Affected Roads in AOI (Total {our_r_aoi_aff_km:.2f} km):")
    print(f"     - Within 30m of EMS affected roads:                         {our_r_matched_km:.2f} km ({our_r_matched_km/our_r_aoi_aff_km*100:.1f}%)")

    # 6. Syabru Besi Validation Overlay Plot (Strictly Georeferenced)
    cx, cy = 337320.0, 3115840.0
    half_w = 2000.0
    xmin, xmax = cx - half_w, cx + half_w
    ymin, ymax = cy - half_w, cy + half_w

    with rasterio.open("data/processed/hazard_classes.tif") as src_haz:
        trans = src_haz.transform

    fig, ax = plt.subplots(figsize=(12, 12), dpi=200)

    # Plot accurately georeferenced raster background
    npz_path = "data/interim/s2_cache/post_119_S2B_MSIL2A_20260827T045659_R11.npz"
    extent, _ = plot_raster_background(
        ax,
        npz_path,
        transform=trans,
        clip_extent=(xmin, xmax, ymin, ymax),
        zorder=1
    )

    # Built-in River Centreline Alignment Verification
    draw_osm_river_centreline(ax, target_crs=utm_crs, clip_bounds=(xmin, ymin, xmax, ymax), color="#00e5ff", lw=1.2, zorder=12)

    # EMS Landslide footprint (yellow outline)
    if len(ems_ev) > 0:
        ems_ev_clip = ems_ev.clip_by_rect(xmin, ymin, xmax, ymax)
        ems_ev_clip = ems_ev_clip[~ems_ev_clip.is_empty]
        if len(ems_ev_clip) > 0:
            ems_ev_clip.plot(ax=ax, facecolor=(1.0, 0.9, 0.0, 0.12), edgecolor="#ffe600", linewidth=2.0, zorder=3)

    # Our Class 2 (red outline) & Class 3 (orange outline)
    c3_polys = haz_gdf[haz_gdf["class"] == 3].clip_by_rect(xmin, ymin, xmax, ymax)
    c3_polys = c3_polys[~c3_polys.is_empty]
    if len(c3_polys) > 0:
        c3_polys.plot(ax=ax, facecolor="none", edgecolor="#ff8800", linewidth=1.4, linestyle="--", zorder=4)

    c2_polys = haz_gdf[haz_gdf["class"] == 2].clip_by_rect(xmin, ymin, xmax, ymax)
    c2_polys = c2_polys[~c2_polys.is_empty]
    if len(c2_polys) > 0:
        c2_polys.plot(ax=ax, facecolor="none", edgecolor="#ff2200", linewidth=1.6, zorder=5)

    # EMS TransportationL (cyan lines)
    ems_r_clip = ems_r.cx[xmin:xmax, ymin:ymax]
    if len(ems_r_clip) > 0:
        ems_r_clip.plot(ax=ax, color="#00ffff", linewidth=2.2, linestyle="-.", zorder=6)

    # Our Graded Roads (red/orange)
    our_r_clip = our_r.cx[xmin:xmax, ymin:ymax]
    r_dest = our_r_clip[our_r_clip["damage_grade"] == "Destroyed"]
    r_poss = our_r_clip[our_r_clip["damage_grade"] == "Possibly damaged"]
    if len(r_poss) > 0:
        r_poss.plot(ax=ax, color="#ff8800", linewidth=2.0, linestyle="--", zorder=7)
    if len(r_dest) > 0:
        r_dest.plot(ax=ax, color="#ff0000", linewidth=2.5, zorder=8)

    # 1. EMS BuiltUpP Ground Truth points (yellow circles beneath our graded markers)
    ems_b_clip = ems_b.cx[xmin:xmax, ymin:ymax]
    if len(ems_b_clip) > 0:
        ax.scatter(ems_b_clip.geometry.x, ems_b_clip.geometry.y, color="#ffff00", edgecolor="#333333", s=32, linewidth=0.8, alpha=0.90, zorder=9)

    # 2. Our Graded Buildings: Footprints + Clearly Visible Coloured Squares ON TOP of EMS points
    our_b_clip = our_b.cx[xmin:xmax, ymin:ymax]
    b_dest = our_b_clip[our_b_clip["damage_grade"] == "Destroyed"]
    b_dmg = our_b_clip[our_b_clip["damage_grade"] == "Damaged"]
    b_poss = our_b_clip[our_b_clip["damage_grade"] == "Possibly damaged"]

    # Footprints
    if len(b_poss) > 0:
        b_poss.plot(ax=ax, facecolor="#ffd700", edgecolor="#b38600", linewidth=1.0, alpha=0.45, zorder=10)
    if len(b_dmg) > 0:
        b_dmg.plot(ax=ax, facecolor="#ff8800", edgecolor="#993d00", linewidth=1.2, alpha=0.50, zorder=10)
    if len(b_dest) > 0:
        b_dest.plot(ax=ax, facecolor="#ff0033", edgecolor="#880011", linewidth=1.5, alpha=0.55, zorder=10)

    # Distinct Centroid Squares ON TOP of EMS points
    if len(b_poss) > 0:
        ax.scatter(b_poss.geometry.centroid.x, b_poss.geometry.centroid.y, marker="s", color="#ffd700", edgecolor="black", s=45, linewidth=1.0, zorder=13)
    if len(b_dmg) > 0:
        ax.scatter(b_dmg.geometry.centroid.x, b_dmg.geometry.centroid.y, marker="s", color="#ff7700", edgecolor="black", s=50, linewidth=1.1, zorder=13)
    if len(b_dest) > 0:
        ax.scatter(b_dest.geometry.centroid.x, b_dest.geometry.centroid.y, marker="s", color="#ff0033", edgecolor="black", s=55, linewidth=1.2, zorder=13)

    # Bridges
    ems_br_clip = ems_br.cx[xmin:xmax, ymin:ymax]
    if len(ems_br_clip) > 0:
        ax.scatter(ems_br_clip.geometry.x, ems_br_clip.geometry.y, marker="D", color="#ffff00", edgecolor="black", s=70, linewidth=1.2, zorder=11)

    our_br_clip = our_br.cx[xmin:xmax, ymin:ymax]
    for _, br in our_br_clip.iterrows():
        pt = br.geometry.centroid
        if br["damage_grade"] == "Destroyed":
            ax.plot(pt.x, pt.y, marker="D", color="#ff0044", markeredgecolor="white", markersize=10, markeredgewidth=1.4, zorder=14)
        elif br["damage_grade"] == "Possibly damaged":
            ax.plot(pt.x, pt.y, marker="D", color="#ff8800", markeredgecolor="white", markersize=9, markeredgewidth=1.4, zorder=14)

    # Town center star
    ax.plot(cx, cy, marker="*", color="white", markeredgecolor="black", markersize=14, markeredgewidth=1.5, zorder=16)
    ax.text(
        cx + 60, cy, "Syabru Besi\n(85.343°E, 28.161°N)",
        color="white", fontsize=10, fontweight="bold",
        bbox=dict(boxstyle="round,pad=0.25", facecolor="black", alpha=0.75, edgecolor="none"),
        zorder=16
    )

    ax.set_xlim(extent[0], extent[1])
    ax.set_ylim(extent[2], extent[3])
    ax.axis("off")

    legend_elements = [
        Line2D([0], [0], color="#ffe600", lw=2.5, label="Copernicus EMS Landslide (EMSR927)"),
        Line2D([0], [0], color="#00e5ff", lw=1.2, label="OSM waterway=river (Alignment Check)"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor="#ffff00", markeredgecolor="#333333", markersize=7, label=f"EMS BuiltUpP Points ({len(ems_b)} in AOI)"),
        Line2D([0], [0], marker="s", color="w", markerfacecolor="#ff0033", markeredgecolor="black", markersize=9, label=f"Our Destroyed Buildings ({len(b_dest)} in zoom)"),
        Line2D([0], [0], marker="s", color="w", markerfacecolor="#ff7700", markeredgecolor="black", markersize=8, label=f"Our Damaged Buildings ({len(b_dmg)} in zoom)"),
        Line2D([0], [0], marker="s", color="w", markerfacecolor="#ffd700", markeredgecolor="black", markersize=8, label=f"Our Possibly Damaged Buildings ({len(b_poss)} in zoom)"),
        Line2D([0], [0], color="#00ffff", lw=2.2, linestyle="-.", label=f"EMS TransportationL Roads ({ems_r['length_km'].sum():.1f} km)"),
        Line2D([0], [0], color="#ff0000", lw=2.5, label="Our Destroyed Roads"),
        Line2D([0], [0], color="#ff8800", lw=2.0, linestyle="--", label="Our Possibly Damaged Roads"),
        Line2D([0], [0], marker="D", color="w", markerfacecolor="#ffff00", markeredgecolor="black", markersize=8, label="EMS Bridge (Destroyed)"),
        Line2D([0], [0], marker="D", color="w", markerfacecolor="#ff0044", markeredgecolor="white", markersize=9, label="Our Bridge (Destroyed)"),
        Line2D([0], [0], marker="*", color="w", markeredgecolor="black", markersize=12, label="Syabru Besi Center", linestyle="None")
    ]
    ax.legend(handles=legend_elements, loc="lower left", framealpha=0.92, fontsize=9.0)

    ax.set_title(
        "Layer 4 Validation: Copernicus EMS EMSR927 vs Graded Infrastructure (Syabru Besi 4x4 km)\n"
        f"EMS Buildings Matched <=30m: {ems_matched_aff_30m}/{len(ems_b)} ({pct_ems_matched_aff:.1f}%) | Our Affected Matched: {our_aff_matched_30m}/{len(our_b_aoi_aff)} ({pct_our_aff_matched:.1f}%) | Bridges: {ems_br_matched_30m}/{len(ems_br)} ({pct_ems_br_matched:.0f}%)",
        fontsize=11.0, fontweight="bold", pad=12
    )

    plt.savefig(output_png, bbox_inches="tight")
    plt.close()
    print(f"Validation plot saved to {output_png}")

    # Copy to artifact directory
    artifact_png = Path("/home/zeus/.gemini/antigravity/brain/52dd5215-6165-4f39-8912-cfce41bfdff1/quicklook_validation_l4.png")
    shutil.copy2(output_png, artifact_png)
    print(f"Copied to artifact: {artifact_png}")

    return {
        "ems_matched_aff_30m": ems_matched_aff_30m,
        "total_ems_b": len(ems_b),
        "pct_ems_matched_aff": pct_ems_matched_aff,
        "our_aff_matched_30m": our_aff_matched_30m,
        "total_our_aff_b_aoi": len(our_b_aoi_aff),
        "pct_our_aff_matched": pct_our_aff_matched,
        "ems_br_matched_30m": ems_br_matched_30m,
        "total_ems_br": len(ems_br),
        "pct_ems_br_matched": pct_ems_br_matched,
        "our_br_matched_30m": our_br_matched_30m,
        "total_our_br_aoi": len(our_br_aoi_aff),
        "pct_our_br_matched": pct_our_br_matched,
        "ems_r_matched_km": ems_r_matched_km,
        "ems_r_total_km": ems_r_total_km,
        "our_r_matched_km": our_r_matched_km,
        "our_r_aoi_aff_km": our_r_aoi_aff_km,
    }


if __name__ == "__main__":
    run_validation_l4()
