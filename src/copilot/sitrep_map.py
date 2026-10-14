"""Overview map generator for 1-page Situation Reports (SITREP).

Renders a publication-grade full-width overview map of the complete AOI:
- Shaded relief / hillshade basemap from Copernicus DEM
- OSM waterways and background road network
- Class 2 (observed) and Class 3 (inferred) hazard extents
- Destroyed/flooded road corridors and bridges
- Cut-off and no-ground-access settlements
- Dashed AOI bounding box, scale bar, north arrow, and floating legend
- Bilingual English and Nepali support
- Strictly no nodata black patches, no photo crops, no debug labels
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional
import matplotlib
matplotlib.use("Agg")
matplotlib.rcParams["font.sans-serif"] = ["FreeSans", "DejaVu Sans"]
matplotlib.rcParams["font.family"] = "sans-serif"
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D
import numpy as np
import rasterio
from rasterio.windows import from_bounds


def compute_hillshade(
    dem_array: np.ndarray,
    cell_deg_x: float,
    cell_deg_y: float,
    lat_deg: float,
    az: float = 315.0,
    alt: float = 45.0
) -> np.ndarray:
    """Compute analytical hillshade with metric resolution scaling."""
    rad_az = np.radians(az)
    rad_alt = np.radians(alt)
    dx_m = cell_deg_x * 111320.0 * np.cos(np.radians(lat_deg))
    dy_m = cell_deg_y * 111320.0
    dy, dx = np.gradient(dem_array, dy_m, dx_m)
    slope = np.pi / 2.0 - np.arctan(np.sqrt(dx * dx + dy * dy))
    aspect = np.arctan2(-dx, dy)
    shaded = np.sin(rad_alt) * np.sin(slope) + np.cos(rad_alt) * np.cos(slope) * np.cos(rad_az - aspect)
    return np.clip(shaded, 0.0, 1.0)


def generate_sitrep_overview_map(run_dir: Path, out_png_path: Path, lang: str = "en") -> Path:
    """Generate high-resolution full-width overview map for 1-page SitRep."""
    is_ne = (lang == "ne")
    run_dir = Path(run_dir).resolve()
    proc = run_dir / "processed"
    routing = proc / "routing"
    raw = run_dir / "raw"

    # 1. Summary metadata for bbox & terrain regime
    sum_p = run_dir / "run_summary.json"
    sum_data = json.loads(sum_p.read_text(encoding="utf-8")) if sum_p.exists() else {}
    bbox = sum_data.get("bbox", [0.0, 0.0, 0.0, 0.0])
    min_lon, min_lat, max_lon, max_lat = bbox
    raw_regime = sum_data.get("terrain_regime") or ("flat_floodplain" if "assam" in run_dir.name.lower() else "steep_valley")
    is_flat = (raw_regime == "flat_floodplain")

    # Match 2.45:1 landscape banner ratio so the map fills the full page width
    center_lat = (min_lat + max_lat) / 2.0
    center_lon = (min_lon + max_lon) / 2.0
    cos_lat = np.cos(np.radians(center_lat))
    h_deg = max_lat - min_lat
    w_deg = max_lon - min_lon
    metric_h = max(h_deg, 0.01)
    metric_w = max(w_deg * cos_lat, 0.01)
    cur_aspect = metric_w / metric_h

    target_aspect = 2.45
    if cur_aspect < target_aspect:
        needed_metric_w = metric_h * target_aspect
        needed_w_deg = needed_metric_w / cos_lat
        v_min_lon = center_lon - needed_w_deg / 2.0
        v_max_lon = center_lon + needed_w_deg / 2.0
        v_min_lat = min_lat - h_deg * 0.03
        v_max_lat = max_lat + h_deg * 0.03
    else:
        needed_metric_h = metric_w / target_aspect
        v_min_lat = center_lat - needed_metric_h / 2.0
        v_max_lat = center_lat + needed_metric_h / 2.0
        v_min_lon = min_lon - w_deg * 0.03
        v_max_lon = max_lon + w_deg * 0.03

    fig_w = 9.8
    fig_h = fig_w / target_aspect

    fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=180)
    fig.patch.set_facecolor("#f8fafc")
    ax.set_facecolor("#f1f5f9")

    # 2. Hillshade Basemap from dem_buffered.tif
    dem_p = raw / "dem" / "dem_buffered.tif"
    has_dem = False
    if dem_p.exists():
        try:
            with rasterio.open(dem_p) as src:
                win = from_bounds(v_min_lon, v_min_lat, v_max_lon, v_max_lat, src.transform)
                dem_data = src.read(1, window=win, boundless=True, fill_value=0.0)
                dem_data = np.nan_to_num(dem_data, nan=0.0)
                if dem_data.max() > dem_data.min() + 5:
                    res_x = abs(src.transform[0])
                    res_y = abs(src.transform[4])
                    lat_mid = (v_min_lat + v_max_lat) / 2.0
                    hs = compute_hillshade(dem_data, res_x, res_y, lat_mid)
                    ax.imshow(hs, cmap="gray", extent=[v_min_lon, v_max_lon, v_min_lat, v_max_lat], origin="upper", alpha=0.60, zorder=1)
                    has_dem = True
        except Exception:
            pass

    if not has_dem:
        ax.axhspan(v_min_lat, v_max_lat, color="#e2e8f0", zorder=1)

    # 3. Waterways (light blue lines)
    ww_p = raw / "osm" / "osm_waterways.geojson"
    if ww_p.exists():
        try:
            ww_data = json.loads(ww_p.read_text(encoding="utf-8"))
            for feat in ww_data.get("features", []):
                geom = feat.get("geometry", {})
                gtype = geom.get("type")
                coords = geom.get("coordinates", [])
                if gtype == "LineString" and coords:
                    xs, ys = zip(*coords)
                    ax.plot(xs, ys, color="#38bdf8", linewidth=1.2, alpha=0.7, zorder=2)
                elif gtype == "MultiLineString":
                    for sub in coords:
                        if sub:
                            xs, ys = zip(*sub)
                            ax.plot(xs, ys, color="#38bdf8", linewidth=1.2, alpha=0.7, zorder=2)
        except Exception:
            pass

    # 4. Intact Road Network (faint gray)
    roads_p = proc / "roads_graded.geojson"
    if roads_p.exists():
        try:
            r_data = json.loads(roads_p.read_text(encoding="utf-8"))
            for feat in r_data.get("features", []):
                geom = feat.get("geometry", {})
                props = feat.get("properties", {})
                coords = geom.get("coordinates", [])
                gtype = geom.get("type")
                if props.get("damage_grade") not in ["Destroyed", "Flooded"]:
                    if gtype == "LineString" and coords:
                        xs, ys = zip(*coords)
                        ax.plot(xs, ys, color="#94a3b8", linewidth=0.6, alpha=0.45, zorder=3)
                    elif gtype == "MultiLineString":
                        for sub in coords:
                            if sub:
                                xs, ys = zip(*sub)
                                ax.plot(xs, ys, color="#94a3b8", linewidth=0.6, alpha=0.45, zorder=3)
        except Exception:
            pass

    # 5. Hazard Polygons (Class 2 & Class 3)
    haz_p = proc / "hazard_polygons.geojson"
    if haz_p.exists():
        try:
            from matplotlib.patches import Polygon as MplPolygon
            from matplotlib.collections import PatchCollection
            h_data = json.loads(haz_p.read_text(encoding="utf-8"))
            c2_patches = []
            c3_patches = []
            for feat in h_data.get("features", []):
                props = feat.get("properties", {})
                cls = props.get("class")
                geom = feat.get("geometry", {})
                gtype = geom.get("type")
                coords = geom.get("coordinates", [])
                if gtype == "Polygon":
                    if coords and len(coords[0]) >= 3:
                        poly = MplPolygon(coords[0], closed=True)
                        if cls == 2: c2_patches.append(poly)
                        elif cls == 3: c3_patches.append(poly)
                elif gtype == "MultiPolygon":
                    for poly_coords in coords:
                        if poly_coords and len(poly_coords[0]) >= 3:
                            poly = MplPolygon(poly_coords[0], closed=True)
                            if cls == 2: c2_patches.append(poly)
                            elif cls == 3: c3_patches.append(poly)

            if c3_patches:
                pc3 = PatchCollection(c3_patches, facecolor="#fbbf24", edgecolor="#d97706", linewidth=0.5, alpha=0.45, zorder=4)
                ax.add_collection(pc3)
            if c2_patches:
                c2_col = "#0284c7" if is_flat else "#dc2626"
                c2_edge = "#0369a1" if is_flat else "#991b1b"
                pc2 = PatchCollection(c2_patches, facecolor=c2_col, edgecolor=c2_edge, linewidth=0.8, alpha=0.65, zorder=5)
                ax.add_collection(pc2)
        except Exception:
            pass

    # 6. Destroyed / Flooded Roads (bold red)
    if roads_p.exists():
        try:
            r_data = json.loads(roads_p.read_text(encoding="utf-8"))
            for feat in r_data.get("features", []):
                geom = feat.get("geometry", {})
                props = feat.get("properties", {})
                coords = geom.get("coordinates", [])
                gtype = geom.get("type")
                if props.get("damage_grade") in ["Destroyed", "Flooded"]:
                    if gtype == "LineString" and coords:
                        xs, ys = zip(*coords)
                        ax.plot(xs, ys, color="#b91c1c", linewidth=2.2, zorder=6)
                    elif gtype == "MultiLineString":
                        for sub in coords:
                            if sub:
                                xs, ys = zip(*sub)
                                ax.plot(xs, ys, color="#b91c1c", linewidth=2.2, zorder=6)
        except Exception:
            pass

    # 7. Destroyed / Flooded Bridges (red diamonds)
    br_p = proc / "bridges_graded.geojson"
    if br_p.exists():
        try:
            br_data = json.loads(br_p.read_text(encoding="utf-8"))
            br_xs, br_ys = [], []
            for feat in br_data.get("features", []):
                props = feat.get("properties", {})
                if props.get("damage_grade") in ["Destroyed", "Flooded"]:
                    geom = feat.get("geometry", {})
                    c = geom.get("coordinates", [None, None])
                    if c[0] is not None:
                        br_xs.append(c[0])
                        br_ys.append(c[1])
            if br_xs:
                ax.scatter(br_xs, br_ys, marker="D", s=45, color="#991b1b", edgecolor="#ffffff", linewidth=0.9, zorder=7)
        except Exception:
            pass

    # 8. Settlements (Cut-off & No ground access)
    settle_p = routing / "settlements.geojson"
    if settle_p.exists():
        try:
            s_data = json.loads(settle_p.read_text(encoding="utf-8"))
            cut_veh_xs, cut_veh_ys = [], []
            no_gnd_xs, no_gnd_ys = [], []
            for feat in s_data.get("features", []):
                props = feat.get("properties", {})
                geom = feat.get("geometry", {})
                c = geom.get("coordinates", [None, None])
                if c[0] is not None:
                    is_v_cut = (props.get("vehicle_status_opt") == "cut_off")
                    is_w_cut = (props.get("walking_status_opt") == "cut_off")
                    if is_v_cut and is_w_cut:
                        no_gnd_xs.append(c[0])
                        no_gnd_ys.append(c[1])
                    elif is_v_cut:
                        cut_veh_xs.append(c[0])
                        cut_veh_ys.append(c[1])
            if cut_veh_xs:
                ax.scatter(cut_veh_xs, cut_veh_ys, marker="o", s=32, color="#ea580c", edgecolor="#ffffff", linewidth=0.8, zorder=8)
            if no_gnd_xs:
                ax.scatter(no_gnd_xs, no_gnd_ys, marker="^", s=55, color="#7c3aed", edgecolor="#ffffff", linewidth=1.0, zorder=9)
        except Exception:
            pass

    # 9. AOI Bounding Box Outline (clean dashed)
    aoi_rect = plt.Rectangle((min_lon, min_lat), max_lon - min_lon, max_lat - min_lat,
                             linewidth=1.2, edgecolor="#475569", facecolor="none", linestyle="--", zorder=10)
    ax.add_patch(aoi_rect)

    # 10. North Arrow & Scale Bar
    na_x = v_min_lon + (v_max_lon - v_min_lon) * 0.04
    na_y = v_max_lat - (v_max_lat - v_min_lat) * 0.08
    ax.annotate("N", xy=(na_x, na_y), xytext=(na_x, na_y - (v_max_lat - v_min_lat) * 0.07),
                arrowprops=dict(facecolor="#0f172a", edgecolor="#0f172a", width=1.5, headwidth=6),
                ha="center", va="center", fontsize=8, fontweight="bold", color="#0f172a", zorder=12)

    sb_len_km = 5.0 if (max_lon - min_lon) > 0.25 else 2.0
    lat_mid = (v_min_lat + v_max_lat) / 2.0
    deg_per_km = 1.0 / (111.32 * np.cos(np.radians(lat_mid)))
    sb_deg = sb_len_km * deg_per_km
    sb_x0 = v_min_lon + (v_max_lon - v_min_lon) * 0.04
    sb_y0 = v_min_lat + (v_max_lat - v_min_lat) * 0.06
    ax.plot([sb_x0, sb_x0 + sb_deg], [sb_y0, sb_y0], color="#0f172a", linewidth=2.5, zorder=12)
    lbl_scale = f"{int(sb_len_km)} km" if not is_ne else f"{int(sb_len_km)} कि.मी."
    ax.text(sb_x0 + sb_deg / 2.0, sb_y0 + (v_max_lat - v_min_lat) * 0.02, lbl_scale,
            ha="center", va="bottom", fontsize=6.5, fontweight="bold", color="#0f172a", zorder=12)

    # 11. Clean In-Map Floating Legend
    leg_hazard_lbl = "बाढी क्षेत्र (प्रत्यक्ष)" if is_ne else ("Flood water (observed)" if is_flat else "Observed hazard")
    leg_inf_lbl = "अनुमानित बहाव" if is_ne else "Inferred hazard"
    leg_road_lbl = "जलमग्न सडक" if is_ne and is_flat else ("नष्ट सडक" if is_ne else ("Flooded road" if is_flat else "Destroyed road"))
    leg_br_lbl = "जलमग्न पुल" if is_ne and is_flat else ("नष्ट पुल" if is_ne else ("Flooded bridge" if is_flat else "Destroyed bridge"))
    leg_cut_lbl = "सवारी सम्पर्कविहीन" if is_ne else "Road cut-off settlement"
    leg_nognd_lbl = "पूर्ण स्थल सम्पर्कविहीन" if is_ne else "No ground access (dual severed)"
    leg_aoi_lbl = "अध्ययन क्षेत्र (AOI)" if is_ne else "Assessment AOI"

    haz_col = "#0284c7" if is_flat else "#dc2626"
    legend_elements = [
        mpatches.Patch(facecolor=haz_col, edgecolor="none", alpha=0.75, label=leg_hazard_lbl),
        mpatches.Patch(facecolor="#fbbf24", edgecolor="none", alpha=0.55, label=leg_inf_lbl),
        Line2D([0], [0], color="#b91c1c", lw=2.2, label=leg_road_lbl),
        Line2D([0], [0], marker="D", color="w", markerfacecolor="#991b1b", markeredgecolor="w", markersize=6, label=leg_br_lbl),
        Line2D([0], [0], marker="o", color="w", markerfacecolor="#ea580c", markeredgecolor="w", markersize=6, label=leg_cut_lbl),
        Line2D([0], [0], marker="^", color="w", markerfacecolor="#7c3aed", markeredgecolor="w", markersize=7, label=leg_nognd_lbl),
        Line2D([0], [0], color="#475569", lw=1.2, linestyle="--", label=leg_aoi_lbl),
    ]

    leg = ax.legend(handles=legend_elements, loc="upper right", fontsize=6, framealpha=0.92,
                    edgecolor="#cbd5e1", facecolor="#ffffff", handlelength=1.5, borderpad=0.4, labelspacing=0.3)
    leg.set_zorder(15)

    ax.set_xlim(v_min_lon, v_max_lon)
    ax.set_ylim(v_min_lat, v_max_lat)
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_edgecolor("#94a3b8")
        spine.set_linewidth(0.8)

    plt.subplots_adjust(left=0.01, right=0.99, top=0.99, bottom=0.01)
    out_png_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(str(out_png_path), dpi=180, facecolor=fig.get_facecolor(), bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)
    return out_png_path
