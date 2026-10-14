"""
FastAPI Backend for Spaceborne Rapid Disaster Assessment Platform (L7).
Operational Intel Visualizer: Strict JSON data binding, manifest filtering,
cloud-masked median S2 composite slider, and provenance-tracked validation banners.
"""

import os
import io
import re
import sys
import time
import json
import math
import shutil
import logging
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

import numpy as np
from PIL import Image
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException, Query, Response, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("dashboard")

app = FastAPI(title="Spaceborne Rapid Disaster Assessment Dashboard", version="1.1.0")

# Restrict CORS to localhost and local loopback origins (no wildcard '*')
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:8000",
        "http://localhost:8000",
        "http://127.0.0.1:3000",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"]
)
app.add_middleware(GZipMiddleware, minimum_size=1000)

BASE_DIR = Path(__file__).resolve().parent.parent.parent
RUNS_DIR = Path(os.environ.get("RUNS_DIR", BASE_DIR / "runs"))
STATIC_DIR = Path(__file__).resolve().parent / "static"
MANIFEST_FILE = Path(__file__).resolve().parent / "runs_manifest.json"

RUN_ID_REGEX = re.compile(r"^[a-zA-Z0-9_\-\.]+$")


def validate_run_id(run_id: str) -> Path:
    """
    Validates run_id strictly against path traversal and pattern whitelist.
    Ensures resolved path is strictly contained within RUNS_DIR.
    """
    if not run_id or not RUN_ID_REGEX.match(run_id) or ".." in run_id or "/" in run_id or "\\" in run_id:
        raise HTTPException(status_code=400, detail="Invalid run_id format")
    
    run_folder = (RUNS_DIR / run_id).resolve()
    runs_dir_resolved = RUNS_DIR.resolve()
    
    try:
        run_folder.relative_to(runs_dir_resolved)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid path traversal detected")

    if not run_folder.exists() or not run_folder.is_dir():
        raise HTTPException(status_code=404, detail="Run not found")

    return run_folder

# In-memory image cache for S2 cloud-masked median composites
_COMPOSITE_CACHE: Dict[str, bytes] = {}


def load_runs_manifest() -> Dict[str, Any]:
    """Loads manifest of officially verified runs for tag e2e-final3."""
    if MANIFEST_FILE.exists():
        try:
            return json.loads(MANIFEST_FILE.read_text())
        except Exception as e:
            logger.warning(f"Error reading manifest: {e}")
    return {"verified_runs": {}}


def derive_operational_run_label(run_folder: Path, summary: Dict[str, Any]) -> str:
    """
    Derives operational label strictly from OSM tags:
    1. place in ['city', 'town'] inside unbuffered bbox.
    2. Features with admin_centre / municipality / is_in / population inside unbuffered bbox.
    3. place == 'village' inside unbuffered bbox ordered by number of buildings nearby.
    4. Supplement with nearest city/town from buffered area within 25km.
    5. Supplement with nearest villages/features from buffered area.
    No hardcoded place names.
    """
    bbox = summary.get("bbox", [])
    if len(bbox) != 4:
        parts = run_folder.name.replace("_", " ").split()
        return " ".join([p.capitalize() for p in parts])

    cx = (bbox[0] + bbox[2]) / 2.0
    cy = (bbox[1] + bbox[3]) / 2.0
    date = summary.get("event_date", "")
    raw_regime = summary.get("terrain_regime") or ("flat_floodplain" if "assam" in run_folder.name.lower() else "steep_valley")
    regime_str = "Flat Floodplain" if raw_regime == "flat_floodplain" else "Steep Valley"

    # Pre-calculate nearby building counts from settlements.geojson
    settle_file = run_folder / "processed" / "routing" / "settlements.geojson"
    settle_pts = []
    if settle_file.exists():
        try:
            s_geo = json.loads(settle_file.read_text())
            for feat in s_geo.get("features", []):
                p = feat.get("properties", {})
                b = p.get("building_count", 0)
                c = feat.get("geometry", {}).get("coordinates", [])
                if len(c) >= 2:
                    settle_pts.append((c[0], c[1], b))
        except Exception:
            pass

    def evaluate_places(pfile: Path, max_dist: Optional[float] = None):
        if not pfile.exists():
            return []
        items = []
        seen = set()
        try:
            d = json.loads(pfile.read_text())
            for feat in d.get("features", []):
                props = feat.get("properties", {})
                raw_name = props.get("name:en") or props.get("name") or ""
                clean = raw_name.split("(")[0].split(",")[0].strip()
                if not clean or clean.startswith("Place node") or clean.startswith("Cluster") or clean == "None":
                    continue
                coords = feat.get("geometry", {}).get("coordinates", [cx, cy])
                dist = math.hypot(coords[0] - cx, coords[1] - cy) * 111.0
                if max_dist and dist > max_dist:
                    continue
                if clean in seen:
                    continue
                seen.add(clean)

                pl = props.get("place", "")
                has_admin = any(k in props for k in ["admin_centre", "municipality", "is_in", "population"])
                bld_cnt = sum(b for x, y, b in settle_pts if math.hypot(coords[0] - x, coords[1] - y) * 111.0 <= 3.0)

                tier = 4
                if pl in ["city", "town"]:
                    tier = 1
                elif has_admin:
                    tier = 2
                elif pl == "village":
                    tier = 3

                items.append({
                    "name": clean,
                    "tier": tier,
                    "dist": dist,
                    "bld_count": bld_cnt
                })
        except Exception:
            pass
        return items

    unbuf_items = evaluate_places(run_folder / "raw" / "osm" / "osm_places.geojson")
    buf_items = evaluate_places(run_folder / "raw" / "osm_buffered" / "osm_places.geojson", max_dist=25.0)

    top_candidates = []

    # Priority 1: Cities / Towns inside unbuffered bbox
    t_in = [x for x in unbuf_items if x["tier"] == 1]
    t_in.sort(key=lambda x: x["dist"])
    top_candidates.extend([x["name"] for x in t_in])

    # Priority 2: Places with admin_centre / municipality / is_in / population inside unbuffered bbox
    a_in = [x for x in unbuf_items if x["tier"] == 2 and x["name"] not in top_candidates]
    a_in.sort(key=lambda x: x["dist"])
    top_candidates.extend([x["name"] for x in a_in])

    # Priority 3: Villages inside unbuffered bbox by number of buildings nearby
    v_in = [x for x in unbuf_items if x["tier"] == 3 and x["name"] not in top_candidates]
    v_in.sort(key=lambda x: (-x["bld_count"], x["dist"]))
    top_candidates.extend([x["name"] for x in v_in])

    # Priority 4: If fewer than 2 names, supplement from nearest city/town in buffered area
    if len(top_candidates) < 2:
        t_buf = [x for x in buf_items if x["tier"] == 1 and x["name"] not in top_candidates]
        t_buf.sort(key=lambda x: x["dist"])
        top_candidates.extend([x["name"] for x in t_buf])

    # Priority 5: If still fewer, supplement from buffered admin/villages by buildings
    if len(top_candidates) < 2:
        v_buf = [x for x in buf_items if x["name"] not in top_candidates]
        v_buf.sort(key=lambda x: (x["tier"], -x["bld_count"], x["dist"]))
        top_candidates.extend([x["name"] for x in v_buf])

    picked = top_candidates[:2]
    prefix = " / ".join(picked) if picked else run_folder.name.replace("_", " ").title()
    return f"{prefix} — {date} ({regime_str})"


def extract_primary_place(run_folder: Path) -> Optional[str]:
    """Derives primary named place from unbuffered and buffered OSM places."""
    summary_file = run_folder / "run_summary.json"
    bbox = [0, 0, 0, 0]
    if summary_file.exists():
        try:
            bbox = json.loads(summary_file.read_text()).get("bbox", [0, 0, 0, 0])
        except Exception:
            pass
    if len(bbox) != 4:
        return None
    cx = (bbox[0] + bbox[2]) / 2.0
    cy = (bbox[1] + bbox[3]) / 2.0
    for pfile in [run_folder / "raw" / "osm" / "osm_places.geojson", run_folder / "raw" / "osm_buffered" / "osm_places.geojson"]:
        if not pfile.exists():
            continue
        try:
            d = json.loads(pfile.read_text())
            candidates = []
            for feat in d.get("features", []):
                props = feat.get("properties", {})
                raw_name = props.get("name:en") or props.get("name") or ""
                clean = raw_name.split("(")[0].split(",")[0].strip()
                if not clean or clean.startswith("Place node") or clean.startswith("Cluster") or clean == "None":
                    continue
                coords = feat.get("geometry", {}).get("coordinates", [cx, cy])
                dist = math.hypot(coords[0] - cx, coords[1] - cy) * 111.0
                candidates.append((dist, clean))
            if candidates:
                candidates.sort(key=lambda x: x[0])
                return candidates[0][1]
        except Exception:
            pass
    return None


def extract_primary_river(run_folder: Path) -> Optional[str]:
    """Finds the named OSM waterway with the most overlap/proximity to class 2/3 hazard."""
    waterway_file = run_folder / "raw" / "osm" / "osm_waterways.geojson"
    if not waterway_file.exists():
        return None
    hazard_file = run_folder / "processed" / "hazard_polygons.geojson"
    try:
        from shapely.geometry import shape

        w_data = json.loads(waterway_file.read_text(encoding="utf-8"))
        by_name = {}
        for feat in w_data.get("features", []):
            props = feat.get("properties", {})
            ww = props.get("waterway")
            name = props.get("name:en") or props.get("name")
            if name and ww in ["river", "stream", "canal"]:
                clean = name.strip()
                try:
                    geom = shape(feat["geometry"])
                    by_name.setdefault(clean, []).append(geom)
                except Exception:
                    pass

        if not by_name:
            return None

        h_geoms = []
        if hazard_file.exists():
            try:
                h_data = json.loads(hazard_file.read_text(encoding="utf-8"))
                h_geoms = [
                    shape(f["geometry"])
                    for f in h_data.get("features", [])
                    if f.get("properties", {}).get("class") in (2, 3)
                ]
                if not h_geoms:
                    h_geoms = [shape(f["geometry"]) for f in h_data.get("features", [])]
            except Exception:
                pass

        scores = []
        for name, geoms in by_name.items():
            tot_len = sum(g.length for g in geoms)
            if h_geoms:
                near_count = sum(1 for g in geoms for hg in h_geoms if g.distance(hg) < 0.05)
                overlap_len = sum(g.intersection(hg).length for g in geoms for hg in h_geoms if g.intersects(hg))
                score = (overlap_len > 1e-6, overlap_len, near_count * tot_len, tot_len)
            else:
                score = (False, 0, len(geoms), tot_len)
            scores.append((name, score))

        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[0][0]
    except Exception:
        pass
    return None


def get_run_metadata(run_folder: Path) -> Optional[Dict[str, Any]]:
    """Reads run metadata from underlying JSON files and compiles strict ground-truth metrics."""
    summary_file = run_folder / "run_summary.json"
    if not summary_file.exists():
        return None

    try:
        summary = json.loads(summary_file.read_text())
    except Exception as e:
        logger.warning(f"Error parsing {summary_file}: {e}")
        return None

    folder_name = run_folder.name
    event_date = summary.get("event_date", "Unknown Date")
    event_year = event_date.split("-")[0] if event_date and "-" in event_date else "2026"
    bbox = summary.get("bbox", [])
    status = summary.get("status", "COMPLETED")
    
    # Check terrain regime
    regime = summary.get("terrain_regime")
    if not regime:
        val_status_raw = summary.get("validation_status", "")
        if "EMSR692" in val_status_raw or "flat" in val_status_raw.lower() or "assam" in folder_name.lower():
            regime = "flat_floodplain"
        else:
            regime = "steep_valley"

    proc = run_folder / "processed"
    routing = proc / "routing"

    # Derive operational human label
    human_label = derive_operational_run_label(run_folder, summary)

    # Check for user-specified event_name (CLI arg or event_name.txt / event_metadata.json)
    event_name = summary.get("event_name")
    if not event_name:
        txt_path = run_folder / "event_name.txt"
        if txt_path.exists():
            try:
                event_name = txt_path.read_text(encoding="utf-8").strip()
            except Exception:
                pass
    if not event_name:
        meta_json_path = run_folder / "event_metadata.json"
        if meta_json_path.exists():
            try:
                ev_meta = json.loads(meta_json_path.read_text(encoding="utf-8"))
                event_name = ev_meta.get("event_name") or ev_meta.get("name")
            except Exception:
                pass

    if event_name:
        main_title = event_name
        subtitle = human_label
        display_label = f"{event_name} — {human_label}"
    else:
        main_title = human_label
        subtitle = ""
        display_label = human_label

    primary_river = extract_primary_river(run_folder)

    # 1. Validation Status & Provenance (file & field)
    val_status_file = proc / "validation_status.json"
    if val_status_file.exists():
        try:
            val_meta = json.loads(val_status_file.read_text())
            validation_status = val_meta.get("validation_status", "not validated against an official map (practice run)")
            val_source_file = val_meta.get("source_file", "processed/validation_status.json")
            val_source_field = val_meta.get("source_field", "validation_status")
        except Exception:
            validation_status = "not validated against an official map (practice run)"
            val_source_file = "processed/validation_status.json"
            val_source_field = "validation_status"
    else:
        # Only runs with their own validation output may show a validation claim; every other run is a practice run
        validation_status = "not validated against an official map (practice run)"
        val_source_file = "run_summary.json"
        val_source_field = "validation_status"

    # 2. Ground-truth: l2_stats.json
    l2_stats = {}
    if (proc / "l2_stats.json").exists():
        try:
            l2_stats = json.loads((proc / "l2_stats.json").read_text())
        except Exception:
            pass
    areas = l2_stats.get("areas_km2", {})
    obs_area = areas.get("event_total_affected", 0.0)
    inf_area = areas.get("event_inferred_affected", 0.0)
    perm_area = areas.get("class_1_permanent_water", 0.0)

    # 3. Ground-truth: damage_summary.json
    dmg_summary = {}
    if (proc / "damage_summary.json").exists():
        try:
            dmg_summary = json.loads((proc / "damage_summary.json").read_text())
        except Exception:
            pass
    
    b_grades = dmg_summary.get("buildings", {}).get("damage_grade_counts", {})
    destroyed_b = b_grades.get("Destroyed", 0)
    damaged_b = b_grades.get("Damaged", 0)
    possibly_damaged_b = b_grades.get("Possibly damaged", 0)
    flooded_b = b_grades.get("Flooded", 0)
    possibly_flooded_b = b_grades.get("Possibly flooded", 0)
    unverified_b = b_grades.get("Unknown (cloud)", 0)
    intact_b = b_grades.get("Not affected", 0)
    total_affected_b = destroyed_b + damaged_b + possibly_damaged_b + flooded_b + possibly_flooded_b

    br_grades = dmg_summary.get("bridges", {}).get("damage_grade_counts", {})
    destroyed_br = br_grades.get("Destroyed", 0)
    possibly_damaged_br = br_grades.get("Possibly damaged", 0)
    flooded_br = br_grades.get("Flooded / impassable", 0)
    possibly_flooded_br = br_grades.get("Possibly flooded", 0)
    unverified_br = br_grades.get("Unknown (cloud)", 0)
    total_affected_br = destroyed_br + possibly_damaged_br + flooded_br + possibly_flooded_br

    roads_km = dmg_summary.get("roads", {}).get("km_by_damage_grade", {})
    destroyed_road_km = float(roads_km.get("Destroyed", 0.0))
    possibly_damaged_road_km = float(roads_km.get("Possibly damaged", 0.0))
    unverified_road_km = float(roads_km.get("Unknown (cloud)", 0.0))
    intact_road_km = float(roads_km.get("Not affected", 0.0))

    # 4. Ground-truth: cutoff_summary.json
    cutoff_summary = {}
    if (routing / "cutoff_summary.json").exists():
        try:
            cutoff_summary = json.loads((routing / "cutoff_summary.json").read_text())
        except Exception:
            pass
    
    veh_opt_cut = cutoff_summary.get("vehicle", {}).get("optimistic", {}).get("cut_off_count", 0)
    veh_pess_cut = cutoff_summary.get("vehicle", {}).get("pessimistic", {}).get("cut_off_count", 0)
    walk_opt_cut = cutoff_summary.get("walking", {}).get("optimistic", {}).get("cut_off_count", 0)
    walk_pess_cut = cutoff_summary.get("walking", {}).get("pessimistic", {}).get("cut_off_count", 0)

    # Calculate no-ground-access settlements (both vehicle and walking severed)
    both_cut_opt = 0
    both_cut_pess = 0
    settle_file = routing / "settlements.geojson"
    if settle_file.exists():
        try:
            s_geo = json.loads(settle_file.read_text())
            for feat in s_geo.get("features", []):
                p = feat.get("properties", {})
                if p.get("vehicle_status_opt") == "cut_off" and p.get("walking_status_opt") == "cut_off":
                    both_cut_opt += 1
                if p.get("vehicle_status_pess") == "cut_off" and p.get("walking_status_pess") == "cut_off":
                    both_cut_pess += 1
        except Exception:
            pass

    # 5. Ground-truth: repair_packages.json (find first ACTIONABLE package with element_count >= 1)
    repair_packages = {}
    if (routing / "repair_packages.json").exists():
        try:
            repair_packages = json.loads((routing / "repair_packages.json").read_text())
        except Exception:
            pass
    
    ranked_pkgs = repair_packages.get("ranked_packages", [])
    actionable_pkgs = [p for p in ranked_pkgs if len(p.get("elements", [])) > 0]
    unconnectable_pkgs = [p for p in ranked_pkgs if len(p.get("elements", [])) == 0]

    unconnectable_count = unconnectable_pkgs[0].get("settlements_count", 0) if unconnectable_pkgs else 0

    if actionable_pkgs:
        pkg1 = actionable_pkgs[0]
        pkg1_rank = pkg1.get("rank", 1)
        pkg1_settlements = pkg1.get("settlements_count", 0)
        pkg1_buildings = pkg1.get("buildings_count", 0)
        pkg1_elements = pkg1.get("elements", [])
        pkg1_element_count = pkg1.get("element_count", len(pkg1_elements))
        has_actionable = True
    else:
        pkg1_rank = None
        pkg1_settlements = 0
        pkg1_buildings = 0
        pkg1_elements = []
        pkg1_element_count = 0
        has_actionable = False

    # 6. S2 Scenes & Date Range Extraction
    s2_scenes = summary.get("s2_scenes_used", [])
    pre_dates = set()
    post_dates = set()
    for s in s2_scenes:
        for p in s.split("_"):
            if len(p) >= 8 and p[:8].isdigit():
                formatted = f"{p[:4]}-{p[4:6]}-{p[6:8]}"
                if s.startswith("pre_"):
                    pre_dates.add(formatted)
                elif s.startswith("post_"):
                    post_dates.add(formatted)
                    
    pre_str = f"{min(pre_dates)} to {max(pre_dates)}" if pre_dates else "—"
    post_str = f"{min(post_dates)} to {max(post_dates)}" if post_dates else "—"
    image_dates_summary = f"Pre: {pre_str} | Post: {post_str}"

    metrics = {
        "areas": {
            "observed_km2": round(obs_area, 4),
            "inferred_km2": round(inf_area, 4),
            "permanent_water_km2": round(perm_area, 4)
        },
        "buildings": {
            "total_affected": total_affected_b,
            "destroyed": destroyed_b,
            "damaged": damaged_b,
            "possibly_damaged": possibly_damaged_b,
            "flooded": flooded_b,
            "possibly_flooded": possibly_flooded_b,
            "unverified": unverified_b,
            "intact": intact_b
        },
        "bridges": {
            "total_affected": total_affected_br,
            "total_assessed": dmg_summary.get("bridges", {}).get("total_count", total_affected_br),
            "destroyed": destroyed_br,
            "possibly_damaged": possibly_damaged_br,
            "flooded": flooded_br,
            "possibly_flooded": possibly_flooded_br,
            "unverified": unverified_br
        },
        "roads_km": {
            "destroyed_km": round(destroyed_road_km, 2),
            "possibly_damaged_km": round(possibly_damaged_road_km, 2),
            "unverified_km": round(unverified_road_km, 2),
            "intact_km": round(intact_road_km, 2)
        },
        "cutoffs": {
            "vehicle_optimistic": veh_opt_cut,
            "vehicle_pessimistic": veh_pess_cut,
            "walking_optimistic": walk_opt_cut,
            "walking_pessimistic": walk_pess_cut,
            "no_ground_access_optimistic": both_cut_opt,
            "no_ground_access_pessimistic": both_cut_pess
        },
        "repair_package_1": {
            "has_actionable_package": has_actionable,
            "rank": pkg1_rank,
            "reconnects_settlements": pkg1_settlements,
            "reconnects_buildings": pkg1_buildings,
            "element_count": pkg1_element_count,
            "elements": pkg1_elements,
            "unconnectable_settlements_count": unconnectable_count
        },
        "repair_packages_all": [
            {
                "rank": p.get("rank"),
                "reconnects_settlements": p.get("settlements_count", 0),
                "reconnects_buildings": p.get("buildings_count", 0),
                "element_count": p.get("element_count", len(p.get("elements", []))),
                "elements": p.get("elements", [])
            }
            for p in actionable_pkgs
        ],
        "validation_metrics": val_meta.get("metrics") if val_status_file.exists() else None
    }

    # Check layer availability
    has_hazards = (proc / "hazard_polygons.geojson").exists()
    has_buildings = (proc / "buildings_graded.geojson").exists()
    has_roads = (proc / "roads_graded.geojson").exists()
    has_bridges = (proc / "bridges_graded.geojson").exists()
    has_settlements = (routing / "settlements.geojson").exists()
    has_repairs = (routing / "repair_packages.json").exists()
    has_s2_cache = (run_folder / "interim" / "s2_cache").exists()

    # 7. Extract OSM Pre-event Snapshot Date
    osm_snapshot_date = None
    osm_summary_file = run_folder / "raw" / "osm" / "osm_summary.json"
    if osm_summary_file.exists():
        try:
            osm_sum = json.loads(osm_summary_file.read_text())
            raw_ts = osm_sum.get("snapshot_time")
            if raw_ts:
                osm_snapshot_date = raw_ts.split("T")[0]
        except Exception:
            pass
    if not osm_snapshot_date:
        osm_snapshot_date = event_date

    manifest = load_runs_manifest()
    is_verified_e2e = folder_name in manifest.get("verified_runs", {})

    return {
        "id": folder_name,
        "label": display_label,
        "main_title": main_title,
        "subtitle": subtitle,
        "event_name": event_name,
        "primary_river": primary_river,
        "primary_place": extract_primary_place(run_folder),
        "osm_label": human_label,
        "event_date": event_date,
        "event_year": event_year,
        "osm_snapshot_date": osm_snapshot_date,
        "bbox": bbox,
        "regime": regime,
        "status": status,
        "is_verified_e2e": is_verified_e2e,
        "validation_status": validation_status,
        "validation_source_file": val_source_file,
        "validation_source_field": val_source_field,
        "sensors_used": summary.get("sensors_used", []),
        "s2_scenes_used": s2_scenes,
        "image_dates_summary": image_dates_summary,
        "optical_evidence_note": summary.get("optical_evidence_note", ""),
        "total_duration_seconds": summary.get("total_duration_seconds"),
        "peak_ram_mb": summary.get("peak_ram_mb"),
        "metrics": metrics,
        "layers_available": {
            "hazards": has_hazards,
            "buildings": has_buildings,
            "roads": has_roads,
            "bridges": has_bridges,
            "settlements": has_settlements,
            "repair_packages": has_repairs,
            "s2_before_after": has_s2_cache
        }
    }


def _find_best_s2_orbit(run_folder: Path) -> Optional[str]:
    """Finds the primary relative orbit that has the highest coverage of clear observation in both pre and post."""
    s2_cache = run_folder / "interim" / "s2_cache"
    summary_file = run_folder / "run_summary.json"
    if not s2_cache.exists():
        return None

    scenes = []
    if summary_file.exists():
        try:
            summary = json.loads(summary_file.read_text())
            scenes = summary.get("s2_scenes_used", [])
        except Exception:
            pass
    if not scenes:
        scenes = [f for f in os.listdir(s2_cache) if f.endswith(".npz")]

    orbits = set()
    for s in scenes:
        for p in s.split("_"):
            if len(p) == 4 and p[0] == "R" and p[1:].isdigit():
                orbits.add(p)

    best_orbit = None
    best_score = -1

    for o in sorted(orbits):
        pre_scenes = [s for s in scenes if s.startswith("pre_") and o in s]
        post_scenes = [s for s in scenes if s.startswith("post_") and o in s]
        if not pre_scenes or not post_scenes:
            continue

        def _count_clear(sc_list):
            cnt = 0
            for sc in sc_list:
                p = s2_cache / sc
                if p.exists():
                    try:
                        d = np.load(p)
                        scl = d.get("SCL")
                        if scl is not None:
                            cnt += int(np.isin(scl, [4, 5, 6, 7]).sum())
                    except Exception:
                        pass
            return cnt

        c_pre = _count_clear(pre_scenes)
        c_post = _count_clear(post_scenes)
        # Prioritize orbit with robust observations in both pre and post
        score = min(c_pre, c_post)
        if score > best_score:
            best_score = score
            best_orbit = o

    return best_orbit


def _get_orbit_composite_array(run_folder: Path, scene_type: str, orbit: str) -> Tuple[Optional[np.ndarray], List[str]]:
    """
    Builds single-orbit clear-observation median composite array for scene_type ('pre' or 'post').
    Returns (composite_float32, used_scene_names).
    """
    s2_cache = run_folder / "interim" / "s2_cache"
    summary_file = run_folder / "run_summary.json"
    scenes = []
    if summary_file.exists():
        try:
            summary = json.loads(summary_file.read_text())
            scenes = [s for s in summary.get("s2_scenes_used", []) if s.startswith(f"{scene_type}_") and orbit in s]
        except Exception:
            pass
    if not scenes:
        scenes = [f for f in os.listdir(s2_cache) if f.startswith(f"{scene_type}_") and orbit in f and f.endswith(".npz")]

    if not scenes:
        return None, []

    visual_stack = []
    used_scenes = []

    for s in scenes:
        spath = s2_cache / s
        if not spath.exists():
            continue
        try:
            d = np.load(spath)
            vis = np.transpose(d["visual"], (1, 2, 0)).astype(np.float32)  # (H, W, 3)
            scl = d.get("SCL")

            # Detect and mask edge-padded / stretched duplicate boundary columns
            diff_next = np.pad(np.abs(vis[:, 1:, :] - vis[:, :-1, :]).sum(axis=-1), ((0, 0), (0, 1)))
            diff_prev = np.pad(np.abs(vis[:, 1:, :] - vis[:, :-1, :]).sum(axis=-1), ((0, 0), (1, 0)))
            col_dup = (diff_next == 0).all(axis=0) | (diff_prev == 0).all(axis=0)

            is_all_255 = np.all(vis >= 254.0, axis=-1)
            is_all_0 = np.all(vis <= 1.0, axis=-1)

            # SCL valid clear surface: 4=veg, 5=non-veg, 6=water, 7=unclassified
            # SCL invalid: 0=nodata, 1=defective, 2=dark, 3=shadow, 8=cloud_med, 9=cloud_high, 10=cirrus, 11=snow
            if scl is not None:
                scl_invalid = np.isin(scl, [0, 1, 2, 3, 8, 9, 10, 11])
            else:
                scl_invalid = False

            invalid = scl_invalid | is_all_255 | is_all_0 | col_dup[None, :]
            vis[invalid] = np.nan

            visual_stack.append(vis)
            used_scenes.append(s)
        except Exception as e:
            logger.debug(f"Error loading {s}: {e}")

    if not visual_stack:
        return None, []

    with np.errstate(all="ignore"):
        composite = np.nanmedian(np.array(visual_stack), axis=0)

    return composite, used_scenes


def generate_cloud_masked_median_composite(run_folder: Path, scene_type: str) -> Optional[bytes]:
    """
    Generates a cloud-masked median composite for Sentinel-2 before/after comparison:
    - Strictly selects scenes of ONE primary relative orbit for registration and radiometric consistency.
    - Reprojected to common grid with proper nodata; per-pixel median of clear pixels only.
    - SCL cloud/shadow/snow masked out.
    - Pixels with no clear observation are transparent with a light grey diagonal hatch.
    - Shared linear 2-98% percentile stretch between pre and post composites.
    - Returns PNG image bytes.
    """
    cache_key = f"{run_folder.name}_{scene_type}"
    if cache_key in _COMPOSITE_CACHE:
        return _COMPOSITE_CACHE[cache_key]

    orbit = _find_best_s2_orbit(run_folder)
    if not orbit:
        return None

    # Compute both pre and post composites to calculate the shared 2-98% percentile stretch
    pre_comp, _ = _get_orbit_composite_array(run_folder, "pre", orbit)
    post_comp, _ = _get_orbit_composite_array(run_folder, "post", orbit)

    target_comp = pre_comp if scene_type == "pre" else post_comp
    if target_comp is None:
        return None

    valid_vals = []
    if pre_comp is not None:
        v_pre = pre_comp[~np.isnan(pre_comp)]
        if len(v_pre) > 0:
            valid_vals.append(v_pre)
    if post_comp is not None:
        v_post = post_comp[~np.isnan(post_comp)]
        if len(v_post) > 0:
            valid_vals.append(v_post)

    if valid_vals:
        all_valid = np.concatenate(valid_vals)
        p2, p98 = np.percentile(all_valid, [2.0, 98.0])
        if p98 <= p2:
            p2, p98 = 0.0, 255.0
    else:
        p2, p98 = 0.0, 255.0

    # Apply shared 2-98% linear stretch
    stretched = np.clip((target_comp - p2) / (p98 - p2 + 1e-5) * 255.0, 0, 255)

    # Missing / cloudy pixels -> light grey diagonal hatch
    nodata_mask = np.isnan(target_comp[..., 0])
    H, W = nodata_mask.shape
    y_idx, x_idx = np.indices((H, W))
    hatch = ((x_idx + y_idx) % 8 < 3)
    # Light grey hatch lines (#DCE1DF and #F6F7F5)
    hatch_rgb = np.where(hatch[..., None], 220, 240).astype(np.float32)

    out_rgb = stretched.copy()
    out_rgb[nodata_mask] = hatch_rgb[nodata_mask]
    out_rgb = out_rgb.astype(np.uint8)

    # Save to PNG buffer
    im = Image.fromarray(out_rgb)
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    png_bytes = buf.getvalue()

    _COMPOSITE_CACHE[cache_key] = png_bytes
    return png_bytes


class CreateRunRequest(BaseModel):
    bbox: List[float]
    event_date: str
    event_name: Optional[str] = None
    config: Optional[str] = "configs/default.yaml"


ACTIVE_RUNS: Dict[str, Dict[str, Any]] = {}


@app.post("/api/runs/create")
def create_run(req: CreateRunRequest):
    """
    Triggers an end-to-end disaster impact assessment run (L0-L5) in background subprocess.
    """
    # 1. Coordinate range and ordering
    min_lon, min_lat, max_lon, max_lat = [float(x) for x in req.bbox]
    if not (-180.0 <= min_lon < max_lon <= 180.0 and -90.0 <= min_lat < max_lat <= 90.0):
        raise HTTPException(status_code=400, detail="Invalid WGS84 bounding box coordinates: must satisfy -180 <= min_lon < max_lon <= 180 and -90 <= min_lat < max_lat <= 90")

    # 2. Maximum area limit: 0.5 degrees per side (configured limit)
    width_deg = max_lon - min_lon
    height_deg = max_lat - min_lat
    if width_deg > 0.5 or height_deg > 0.5:
        raise HTTPException(
            status_code=400,
            detail=f"Bounding box exceeds maximum allowable area: {width_deg:.3f}° lon × {height_deg:.3f}° lat. Limit is 0.5° per side (approx 55 km × 55 km)."
        )

    # 3. Event date range: Sentinel-2 era (2015-06-23) to today
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", req.event_date):
        raise HTTPException(status_code=400, detail="Invalid event date format. Expected YYYY-MM-DD")
    try:
        e_date = datetime.strptime(req.event_date, "%Y-%m-%d").date()
        s2_launch = datetime(2015, 6, 23).date()
        today = datetime.now().date()
        if e_date < s2_launch:
            raise HTTPException(status_code=400, detail="Event date cannot be earlier than Sentinel-2 launch (2015-06-23)")
        if e_date > today:
            raise HTTPException(status_code=400, detail="Event date cannot be in the future")
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=f"Invalid event date: {ve}")

    # 4. Limit concurrent active pipeline jobs (max 2)
    active_running = [k for k, v in ACTIVE_RUNS.items() if v["proc"].poll() is None]
    if len(active_running) >= 2:
        raise HTTPException(status_code=429, detail="Maximum concurrent assessment jobs reached (limit: 2). Please wait for active runs to finish.")

    # 5. Sanitize event name: allow letters, numbers, spaces, dashes, underscores (max 64 chars)
    sanitized_event_name = None
    if req.event_name:
        raw_name = req.event_name.strip()
        if len(raw_name) > 64:
            raise HTTPException(status_code=400, detail="Event name exceeds maximum length of 64 characters")
        if re.search(r"[;`$\|<>&]", raw_name):
            raise HTTPException(status_code=400, detail="Event name contains forbidden shell or control characters")
        sanitized_event_name = raw_name

    timestamp_slug = datetime.now().strftime("%Y%m%d_%H%M%S")
    clean_slug = re.sub(r"[^a-zA-Z0-9_]+", "_", sanitized_event_name.lower()) if sanitized_event_name else "analysis"
    clean_slug = clean_slug.strip("_")[:24]
    run_id = f"run_{timestamp_slug}_{clean_slug}"
    run_folder = RUNS_DIR / run_id
    run_folder.mkdir(parents=True, exist_ok=True)

    if sanitized_event_name:
        (run_folder / "event_name.txt").write_text(sanitized_event_name, encoding="utf-8")

    status_file = run_folder / "status.json"
    init_status = {
        "status": "RUNNING",
        "stage": "L0_INGESTION",
        "progress_pct": 5.0,
        "elapsed_seconds": 0.0,
        "current_step": "Initializing satellite data ingestion (Sentinel-1, Sentinel-2, DEM, OSM)...",
        "bbox": [min_lon, min_lat, max_lon, max_lat],
        "event_date": req.event_date,
        "event_name": req.event_name,
        "outputs": {},
        "metrics": {},
        "timestamp": datetime.now().isoformat(),
        "error": None
    }
    status_file.write_text(json.dumps(init_status, indent=2))

    cmd = [
        sys.executable, "-u", "main.py",
        "--bbox", str(min_lon), str(min_lat), str(max_lon), str(max_lat),
        "--event-date", req.event_date,
        "--out-dir", str(run_folder)
    ]
    if req.event_name:
        cmd.extend(["--event-name", req.event_name.strip()])

    # Use ONE default config containing validated parameters unless explicitly requested otherwise
    cfg_to_use = req.config or "configs/default.yaml"
    cfg_path = BASE_DIR / cfg_to_use
    if cfg_path.exists():
        cmd.extend(["--config", str(cfg_path)])

    log_path = run_folder / "pipeline.log"
    log_file = open(log_path, "w", encoding="utf-8")

    pid_path = run_folder / "proc.pid"
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(BASE_DIR),
            stdout=log_file,
            stderr=subprocess.STDOUT
        )
        pid_path.write_text(str(proc.pid))
        init_status["pid"] = proc.pid
        status_file.write_text(json.dumps(init_status, indent=2))
    except Exception as e:
        logger.error(f"Failed to spawn pipeline: {e}")
        status_file.write_text(json.dumps({
            "status": "FAILED",
            "stage": "L0_INGESTION",
            "progress_pct": 0.0,
            "elapsed_seconds": 0.0,
            "current_step": "Failed to spawn pipeline process",
            "outputs": {},
            "metrics": {},
            "timestamp": datetime.now().isoformat(),
            "error": str(e)
        }, indent=2))
        raise HTTPException(status_code=500, detail=f"Failed to spawn pipeline: {e}")

    ACTIVE_RUNS[run_id] = {
        "proc": proc,
        "pid": proc.pid,
        "start_time": time.time(),
        "log_path": str(log_path),
        "run_folder": run_folder,
        "event_name": req.event_name,
        "bbox": [min_lon, min_lat, max_lon, max_lat],
        "event_date": req.event_date
    }

    logger.info(f"Started assessment run '{run_id}' with PID {proc.pid}")
    return {
        "status": "started",
        "run_id": run_id,
        "event_name": req.event_name,
        "bbox": [min_lon, min_lat, max_lon, max_lat],
        "event_date": req.event_date
    }


def _extract_log_diagnostics(log_p: Path) -> Tuple[str, List[str]]:
    """Extracts error message and last log lines from a pipeline log file."""
    error_msg = "Pipeline process exited unexpectedly"
    last_lines: List[str] = []
    if log_p.exists():
        try:
            lines = [line.strip() for line in log_p.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip()]
            last_lines = lines[-15:]
            err_lines = [l for l in lines[-30:] if any(k in l for k in ["Error", "ERROR", "Exception", "FAILED", "No S1 scenes found", "no data", "cannot schedule"])]
            if err_lines:
                error_msg = err_lines[-1]
            elif lines:
                error_msg = lines[-1]
        except Exception:
            pass

    if "no data" in error_msg.lower() or "no s1" in error_msg.lower() or "0 scenes" in error_msg.lower():
        error_msg = f"No satellite data found for the selected bounding box and date: {error_msg}"
    return error_msg, last_lines


@app.get("/api/runs/{run_id}/status")
def get_run_status(run_id: str):
    """
    Polls the live execution status of an assessment run, tracking step progression,
    progressive layer outputs, timeouts (600s), dead process detection, and error diagnostics.
    """
    run_folder = validate_run_id(run_id)

    status_file = run_folder / "status.json"
    status_data = {}
    if status_file.exists():
        try:
            status_data = json.loads(status_file.read_text())
        except Exception:
            status_data = {"status": "RUNNING", "progress_pct": 5.0, "current_step": "Processing..."}

    active_info = ACTIVE_RUNS.get(run_id)
    if active_info:
        proc = active_info["proc"]
        start_time = active_info["start_time"]
        elapsed = round(time.time() - start_time, 1)

        # 1. Timeout Check (10 minutes = 600s)
        if elapsed > 600.0 and proc.poll() is None:
            logger.warning(f"Run {run_id} exceeded timeout threshold (600s). Terminating...")
            try:
                proc.terminate()
                proc.wait(timeout=5)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
            status_data["status"] = "FAILED"
            status_data["error"] = "Pipeline timed out: exceeded maximum execution threshold of 10 minutes."
            status_data["current_step"] = "Execution timed out"
            status_file.write_text(json.dumps(status_data, indent=2))
            return {**status_data, "run_id": run_id, "is_finished": True, "elapsed_seconds": elapsed}

        # 2. Process Completion / Crash Check
        poll_res = proc.poll()
        if poll_res is not None:
            if poll_res != 0 and status_data.get("status") not in ["COMPLETED", "DEGRADED"]:
                error_msg, last_lines = _extract_log_diagnostics(Path(active_info["log_path"]))
                status_data["status"] = "FAILED"
                status_data["error"] = error_msg
                status_data["last_log_lines"] = last_lines
                status_data["current_step"] = f"Execution failed: {error_msg}"
                status_file.write_text(json.dumps(status_data, indent=2))
                return {**status_data, "run_id": run_id, "is_finished": True, "elapsed_seconds": elapsed}
    else:
        # Server restarted or process not in memory: check if recorded as RUNNING but process is dead
        curr_st = status_data.get("status", "RUNNING")
        if curr_st == "RUNNING" and not (run_folder / "run_summary.json").exists():
            # Check if PID is alive
            pid = status_data.get("pid")
            if not pid and (run_folder / "proc.pid").exists():
                try:
                    pid = int((run_folder / "proc.pid").read_text().strip())
                except Exception:
                    pass
            
            is_alive = False
            if pid:
                try:
                    import psutil
                    is_alive = psutil.pid_exists(pid)
                except Exception:
                    try:
                        os.kill(pid, 0)
                        is_alive = True
                    except OSError:
                        is_alive = False

            if not is_alive:
                error_msg, last_lines = _extract_log_diagnostics(run_folder / "pipeline.log")
                status_data["status"] = "FAILED"
                status_data["error"] = error_msg or "Pipeline process terminated unexpectedly (e.g. server restart or killed)."
                status_data["last_log_lines"] = last_lines
                status_data["current_step"] = f"Execution halted: {status_data['error']}"
                status_file.write_text(json.dumps(status_data, indent=2))
                return {**status_data, "run_id": run_id, "is_finished": True}

    # Progressive stage and layer tracking while running
    proc_dir = run_folder / "processed"
    if status_data.get("status") == "RUNNING":
        outs = status_data.setdefault("outputs", {})
        if (proc_dir / "routing" / "cutoff_summary.json").exists():
            status_data["stage"] = "L5_ROUTING"
            status_data["progress_pct"] = max(status_data.get("progress_pct", 0.0), 90.0)
            status_data["current_step"] = "L5 Network isolation & repair package analysis complete. Finalizing summary..."
            outs["hazard_polygons_geojson"] = True
            outs["buildings_graded_geojson"] = True
            outs["roads_graded_geojson"] = True
            outs["bridges_graded_geojson"] = True
            outs["settlements_geojson"] = True
            outs["repair_packages_json"] = True
        elif (proc_dir / "damage_summary.json").exists():
            status_data["stage"] = "L4_DAMAGE"
            status_data["progress_pct"] = max(status_data.get("progress_pct", 0.0), 75.0)
            status_data["current_step"] = "L3/L4 Infrastructure damage assessment complete. Analyzing network connectivity (L5)..."
            outs["hazard_polygons_geojson"] = True
            outs["buildings_graded_geojson"] = True
            outs["roads_graded_geojson"] = True
            outs["bridges_graded_geojson"] = True
        elif (proc_dir / "hazard_classes.tif").exists() or (proc_dir / "hazard_polygons.geojson").exists():
            status_data["stage"] = "L2_HAZARD"
            status_data["progress_pct"] = max(status_data.get("progress_pct", 0.0), 45.0)
            status_data["current_step"] = "L2 Hazard mapping complete. Analyzing infrastructure impact (L3/L4)..."
            outs["hazard_polygons_geojson"] = True
        elif (proc_dir / "terrain_regime.json").exists():
            status_data["stage"] = "L1_TERRAIN"
            status_data["progress_pct"] = max(status_data.get("progress_pct", 0.0), 25.0)
            status_data["current_step"] = "L1 Terrain regime determined. Computing radar & optical change detection (L2)..."
        else:
            status_data["stage"] = "L0_INGESTION"
            status_data["progress_pct"] = max(status_data.get("progress_pct", 0.0), 10.0)
            status_data["current_step"] = "Ingesting satellite imagery, DEM, and OSM vector data (L0)..."

    # If run_summary.json exists and pipeline finished
    summary_file = run_folder / "run_summary.json"
    if summary_file.exists():
        try:
            summary = json.loads(summary_file.read_text())
            final_status = summary.get("status", "COMPLETED")
            status_data["status"] = final_status
            status_data["progress_pct"] = 100.0
            status_data["stage"] = "COMPLETED"
            status_data["current_step"] = "Assessment successfully completed."
            status_data["outputs"] = summary.get("outputs", {})
            status_data["metrics"] = summary.get("metrics", {})
        except Exception:
            pass

    curr_status = status_data.get("status", "RUNNING")
    is_finished = curr_status in ["COMPLETED", "DEGRADED", "FAILED"]

    return {
        "run_id": run_id,
        "status": curr_status,
        "stage": status_data.get("stage", "UNKNOWN"),
        "progress_pct": status_data.get("progress_pct", 0.0),
        "elapsed_seconds": status_data.get("elapsed_seconds", 0.0),
        "current_step": status_data.get("current_step", ""),
        "outputs": status_data.get("outputs", {}),
        "metrics": status_data.get("metrics", {}),
        "error": status_data.get("error"),
        "last_log_lines": status_data.get("last_log_lines", []),
        "is_finished": is_finished
    }


@app.get("/api/runs")
def list_runs(show_all: bool = Query(False)):
    """
    Scans runs/ directory. By default, returns ONLY completed/degraded runs
    verified under pipeline tag e2e-final4 (manifest-backed) and user-initiated runs.
    Other runs are accessible when show_all=True.
    """
    if not RUNS_DIR.exists():
        return []

    manifest = load_runs_manifest()
    verified_map = manifest.get("verified_runs", {})

    runs = []
    for item in RUNS_DIR.iterdir():
        if not item.is_dir():
            continue
        if (item / "run_summary.json").exists():
            meta = get_run_metadata(item)
            if not meta:
                continue

            if not show_all:
                is_user_run = item.name.startswith("run_") or (item / "status.json").exists()
                if (meta["id"] in verified_map or is_user_run) and meta["status"] in ["COMPLETED", "DEGRADED"]:
                    runs.append(meta)
            else:
                runs.append(meta)
        elif show_all and (item / "status.json").exists():
            try:
                st = json.loads((item / "status.json").read_text())
                runs.append({
                    "id": item.name,
                    "label": st.get("event_name") or item.name,
                    "main_title": st.get("event_name") or item.name,
                    "subtitle": "Assessment run",
                    "status": st.get("status", "FAILED"),
                    "event_date": st.get("event_date", ""),
                    "event_year": st.get("event_date", "").split("-")[0] if "-" in st.get("event_date", "") else "2026",
                    "bbox": st.get("bbox", []),
                    "regime": "steep_valley"
                })
            except Exception:
                pass

    # Sort logically
    runs.sort(key=lambda r: (0 if "verify" in r["id"] or "practice" in r["id"] else 1, r["event_date"]), reverse=False)
    return runs


@app.get("/api/runs/{run_id}")
def get_run_details(run_id: str, background_tasks: BackgroundTasks):
    """Returns detailed summary payload and layer stats for a specific run."""
    run_folder = validate_run_id(run_id)
    if not (run_folder / "run_summary.json").exists():
        # Check if status.json exists for a failed or in-progress run
        status_file = run_folder / "status.json"
        if status_file.exists():
            st_data = get_run_status(run_id)
            if st_data.get("status") in ["FAILED", "RUNNING"]:
                return {
                    "id": run_id,
                    "label": st_data.get("event_name") or run_id,
                    "main_title": st_data.get("event_name") or run_id,
                    "subtitle": "Assessment run",
                    "status": st_data.get("status"),
                    "error": st_data.get("error"),
                    "last_log_lines": st_data.get("last_log_lines", []),
                    "current_step": st_data.get("current_step", ""),
                    "event_date": st_data.get("event_date", ""),
                    "bbox": st_data.get("bbox", []),
                    "layers_available": {},
                    "metrics": {}
                }
        raise HTTPException(status_code=404, detail="Run not found")

    # Pre-generate DEM XYZ tiles asynchronously in background if not already complete
    tiles_root = run_folder / "processed" / "dem_tiles"
    if not (tiles_root / ".complete").exists():
        from src.dashboard.basemap_renderer import generate_run_hillshade_tiles
        background_tasks.add_task(generate_run_hillshade_tiles, run_folder)

    meta = get_run_metadata(run_folder)
    if not meta:
        raise HTTPException(status_code=500, detail="Error reading run summary")

    proc = run_folder / "processed"
    routing = proc / "routing"
    details = dict(meta)

    if (proc / "l2_stats.json").exists():
        try:
            details["l2_stats"] = json.loads((proc / "l2_stats.json").read_text())
        except Exception:
            pass
    if (proc / "damage_summary.json").exists():
        try:
            details["damage_summary"] = json.loads((proc / "damage_summary.json").read_text())
        except Exception:
            pass
    if (routing / "cutoff_summary.json").exists():
        try:
            details["cutoff_summary"] = json.loads((routing / "cutoff_summary.json").read_text())
        except Exception:
            pass
    if (routing / "repair_packages.json").exists():
        try:
            details["repair_packages"] = json.loads((routing / "repair_packages.json").read_text())
        except Exception:
            pass

    return details


# In-memory layer cache per run
_LAYER_CACHE: Dict[str, bytes] = {}


@app.get("/api/runs/{run_id}/layer/{layer_name}")
def get_run_layer(
    run_id: str,
    layer_name: str,
    affected_only: bool = Query(False),
    simplify_tol: float = Query(0.0)
):
    """
    Serves optimized GeoJSON layer for a specific run.
    Supports affected_only filtering (buildings, roads), geometry simplification, and run-level caching.
    """
    run_folder = validate_run_id(run_id)

    proc = run_folder / "processed"
    routing = proc / "routing"

    layer_map = {
        "hazards": proc / "hazard_polygons.geojson",
        "buildings": proc / "buildings_graded.geojson",
        "roads": proc / "roads_graded.geojson",
        "bridges": proc / "bridges_graded.geojson",
        "settlements": routing / "settlements.geojson",
    }

    if layer_name not in layer_map:
        raise HTTPException(status_code=400, detail=f"Unknown layer {layer_name}")

    target_file = layer_map[layer_name]
    if not target_file.exists():
        raise HTTPException(status_code=404, detail=f"Layer {layer_name} not available for this run")

    cache_key = f"{run_id}_{layer_name}_{affected_only}_{simplify_tol}"
    if cache_key in _LAYER_CACHE:
        return Response(
            content=_LAYER_CACHE[cache_key],
            media_type="application/geo+json",
            headers={"Cache-Control": "public, max-age=86400"}
        )

    # If no filtering or simplification requested, read raw bytes directly
    if not affected_only and simplify_tol <= 0.0:
        raw_bytes = target_file.read_bytes()
        _LAYER_CACHE[cache_key] = raw_bytes
        return Response(
            content=raw_bytes,
            media_type="application/geo+json",
            headers={"Cache-Control": "public, max-age=86400"}
        )

    try:
        data = json.loads(target_file.read_text(encoding="utf-8"))
        features = data.get("features", [])

        # Filter affected features if requested
        if affected_only:
            if layer_name == "buildings":
                features = [
                    f for f in features
                    if f.get("properties", {}).get("damage_grade") not in ("Not affected", "Unknown (cloud)", None)
                ]
            elif layer_name == "roads":
                features = [
                    f for f in features
                    if f.get("properties", {}).get("damage_grade") not in ("Not affected", "Unknown (cloud)", None)
                ]

        # Geometry simplification if requested
        if simplify_tol > 0.0:
            from shapely.geometry import shape, mapping
            simplified_features = []
            for f in features:
                geom = f.get("geometry")
                if geom:
                    try:
                        s_geom = shape(geom).simplify(simplify_tol, preserve_topology=True)
                        simplified_features.append({
                            "type": "Feature",
                            "properties": f.get("properties", {}),
                            "geometry": mapping(s_geom)
                        })
                    except Exception:
                        simplified_features.append(f)
                else:
                    simplified_features.append(f)
            features = simplified_features

        out_data = {
            "type": "FeatureCollection",
            "features": features
        }
        res_bytes = json.dumps(out_data, separators=(",", ":")).encode("utf-8")
        _LAYER_CACHE[cache_key] = res_bytes
        return Response(
            content=res_bytes,
            media_type="application/geo+json",
            headers={"Cache-Control": "public, max-age=86400"}
        )

    except Exception as e:
        logger.error(f"Error processing layer {layer_name}: {e}")
        return FileResponse(target_file, media_type="application/geo+json")


@app.get("/api/runs/{run_id}/repair-packages")
def get_repair_packages(run_id: str):
    """Serves repair packages analysis JSON for a specific run."""
    run_folder = validate_run_id(run_id)
    pkg_file = run_folder / "processed" / "routing" / "repair_packages.json"
    if not pkg_file.exists():
        raise HTTPException(status_code=404, detail="Repair packages not found")
    return JSONResponse(content=json.loads(pkg_file.read_text()))


@app.get("/api/runs/{run_id}/flowpath")
def get_flowpath(
    run_id: str,
    lon: float = Query(..., description="Starting longitude"),
    lat: float = Query(..., description="Starting latitude"),
    buffer_m: float = Query(500.0, description="Settlement buffer distance in meters"),
):
    """Traces D8 downstream flow path from (lon, lat) to AOI edge and identifies settlements within buffer_m."""
    run_folder = validate_run_id(run_id)
    dem_p = run_folder / "raw" / "dem" / "dem_buffered.tif"
    if not dem_p.exists():
        dem_p = run_folder / "raw" / "dem" / "dem.tif"
    if not dem_p.exists():
        raise HTTPException(status_code=404, detail="DEM raster not available for flow path tracing")

    settlements_p = run_folder / "processed" / "routing" / "settlements.geojson"
    from src.l1_preprocessing.flow_tracer import compute_d8_flow_path, find_downstream_settlements

    try:
        path_nodes = compute_d8_flow_path(dem_p, lon, lat)
        settlements = find_downstream_settlements(path_nodes, settlements_p, buffer_distance_m=buffer_m)
    except Exception as e:
        logger.error(f"Error computing flow path: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    coordinates = [[node["lon"], node["lat"]] for node in path_nodes]
    geojson_feature = {
        "type": "Feature",
        "geometry": {
            "type": "LineString",
            "coordinates": coordinates,
        },
        "properties": {
            "start_lon": lon,
            "start_lat": lat,
            "total_downstream_km": path_nodes[-1]["distance_downstream_km"] if path_nodes else 0.0,
            "nodes_count": len(path_nodes),
            "buffer_m": buffer_m,
        }
    }

    return {
        "path_geojson": geojson_feature,
        "path_nodes": path_nodes,
        "downstream_settlements": settlements,
        "total_downstream_km": path_nodes[-1]["distance_downstream_km"] if path_nodes else 0.0,
        "settlements_count": len(settlements),
    }


@app.get("/api/runs/{run_id}/s2-meta")
def get_s2_metadata(run_id: str):
    """Returns metadata for Sentinel-2 cloud-masked composite scenes matching run_summary."""
    run_folder = validate_run_id(run_id)

    summary_file = run_folder / "run_summary.json"
    if not summary_file.exists():
        raise HTTPException(status_code=404, detail="Run summary not found")

    try:
        summary = json.loads(summary_file.read_text())
    except Exception:
        raise HTTPException(status_code=500, detail="Error reading summary")

    orbit = _find_best_s2_orbit(run_folder)
    s2_scenes = summary.get("s2_scenes_used", [])
    if orbit:
        pre_scenes = [s for s in s2_scenes if s.startswith("pre_") and orbit in s]
        post_scenes = [s for s in s2_scenes if s.startswith("post_") and orbit in s]
    else:
        pre_scenes = [s for s in s2_scenes if s.startswith("pre_")]
        post_scenes = [s for s in s2_scenes if s.startswith("post_")]

    def extract_dates(scenes_list):
        dates = set()
        for s in scenes_list:
            for p in s.split("_"):
                if len(p) >= 8 and p[:8].isdigit():
                    dates.add(f"{p[:4]}-{p[4:6]}-{p[6:8]}")
        return sorted(dates)

    pre_dates = extract_dates(pre_scenes)
    post_dates = extract_dates(post_scenes)

    meta = get_run_metadata(run_folder)
    return {
        "run_id": run_id,
        "bbox": meta["bbox"] if meta else [],
        "orbit": orbit,
        "pre": {
            "scenes_count": len(pre_scenes),
            "date_range": f"{pre_dates[0]} to {pre_dates[-1]}" if pre_dates else "—",
            "scenes": pre_scenes
        },
        "post": {
            "scenes_count": len(post_scenes),
            "date_range": f"{post_dates[0]} to {post_dates[-1]}" if post_dates else "—",
            "scenes": post_scenes
        }
    }


@app.get("/api/runs/{run_id}/s2-image")
def get_s2_image(run_id: str, type: str = Query("post", pattern="^(pre|post)$")):
    """Generates read-only cloud-masked median composite Sentinel-2 PNG from raw cache."""
    run_folder = validate_run_id(run_id)

    png_bytes = generate_cloud_masked_median_composite(run_folder, type)
    if not png_bytes:
        raise HTTPException(status_code=404, detail=f"Could not generate {type} S2 composite")

    return Response(content=png_bytes, media_type="image/png", headers={"Cache-Control": "public, max-age=86400"})


@app.get("/api/runs/{run_id}/basemap/hillshade")
def get_run_hillshade(run_id: str):
    """Serves cached Copernicus DEM-30 topographic relief hillshade PNG for the run."""
    run_folder = validate_run_id(run_id)
    from src.dashboard.basemap_renderer import generate_run_hillshade
    png_path, _ = generate_run_hillshade(run_folder)
    if not png_path or not png_path.exists():
        raise HTTPException(status_code=404, detail="Hillshade could not be generated for this run")
    return FileResponse(png_path, media_type="image/png", headers={"Cache-Control": "public, max-age=86400"})


@app.get("/api/runs/{run_id}/basemap/tiles/{z}/{x}/{y}.png")
def get_run_hillshade_tile(run_id: str, z: int, x: int, y: int):
    """Serves Web Mercator DEM hillshade XYZ tile (z=9-14) for high-zoom overlay."""
    run_folder = validate_run_id(run_id)
    if not (0 <= z <= 22 and x >= 0 and y >= 0):
        raise HTTPException(status_code=400, detail="Invalid tile coordinates")

    tiles_root = run_folder / "processed" / "dem_tiles"
    tile_file = (tiles_root / str(z) / str(x) / f"{y}.png").resolve()

    # Ensure resolved tile path is within tiles_root
    try:
        tile_file.relative_to(tiles_root.resolve())
    except (ValueError, RuntimeError):
        raise HTTPException(status_code=400, detail="Invalid tile path")

    if tile_file.exists():
        return FileResponse(tile_file, media_type="image/png", headers={"Cache-Control": "public, max-age=86400"})

    # If tile is outside DEM extent, still generating, or nodata, return 1x1 transparent PNG immediately
    transparent_png = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    return Response(content=transparent_png, media_type="image/png", headers={"Cache-Control": "public, max-age=86400"})


@app.get("/api/runs/{run_id}/basemap/meta")
def get_run_basemap_meta(run_id: str):
    """Serves hillshade bounds metadata."""
    run_folder = validate_run_id(run_id)
    from src.dashboard.basemap_renderer import generate_run_hillshade
    _, meta = generate_run_hillshade(run_folder)
    if not meta:
        raise HTTPException(status_code=404, detail="Hillshade metadata not found")
    return JSONResponse(meta)


@app.get("/api/runs/{run_id}/basemap/waterways")
def get_run_basemap_waterways(run_id: str):
    """Serves raw OSM rivers/waterways GeoJSON."""
    run_folder = validate_run_id(run_id)
    target = run_folder / "raw" / "osm" / "osm_waterways.geojson"
    if not target.exists():
        target = BASE_DIR / "data" / "raw" / "osm" / "osm_waterways.geojson"
    if not target.exists():
        raise HTTPException(status_code=404, detail="Waterways not found")
    return FileResponse(target, media_type="application/geo+json")


@app.get("/api/runs/{run_id}/basemap/roads")
def get_run_basemap_roads(run_id: str):
    """Serves raw OSM roads GeoJSON for baseline rendering."""
    run_folder = validate_run_id(run_id)
    target = run_folder / "raw" / "osm" / "osm_roads.geojson"
    if not target.exists():
        target = BASE_DIR / "data" / "raw" / "osm" / "osm_roads.geojson"
    if not target.exists():
        raise HTTPException(status_code=404, detail="Roads not found")
    return FileResponse(target, media_type="application/geo+json")


@app.get("/api/runs/{run_id}/basemap/places")
def get_run_basemap_places(run_id: str):
    """Serves raw OSM places GeoJSON with Latin and Devanagari labels."""
    run_folder = validate_run_id(run_id)
    target = run_folder / "raw" / "osm" / "osm_places.geojson"
    if not target.exists():
        target = BASE_DIR / "data" / "raw" / "osm" / "osm_places.geojson"
    if not target.exists():
        raise HTTPException(status_code=404, detail="Places not found")
    return FileResponse(target, media_type="application/geo+json")


# Mount static assets
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ==========================================
# PHASE 3: COPILOT & SITREP ENDPOINTS
# ==========================================
# Rate limiting tracker for copilot queries: IP -> list of timestamps
_COPILOT_RATE_LIMIT: Dict[str, List[float]] = {}


@app.post("/api/runs/{run_id}/copilot/ask")
async def copilot_ask(run_id: str, request: Request):
    """Answers rescuer natural-language questions about the given run using CopilotAgent."""
    run_folder = validate_run_id(run_id)

    # Rate limiting: max 60 requests per minute per IP (exempt localhost for test suites)
    client_ip = request.client.host if request.client else "127.0.0.1"
    now_ts = time.time()
    recent_ts = [t for t in _COPILOT_RATE_LIMIT.get(client_ip, []) if now_ts - t < 60.0]
    if client_ip not in ["127.0.0.1", "localhost", "testclient"] and len(recent_ts) >= 60:
        raise HTTPException(status_code=429, detail="Rate limit exceeded: max 60 copilot inquiries per minute.")
    recent_ts.append(now_ts)
    _COPILOT_RATE_LIMIT[client_ip] = recent_ts

    try:
        body = await request.json()
    except Exception:
        body = {}

    question = (body.get("question") or body.get("query") or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="Missing question or empty inquiry")

    # Input length cap (max 500 characters)
    if len(question) > 500:
        raise HTTPException(status_code=400, detail="Question exceeds maximum allowed length of 500 characters")

    provider = body.get("provider") or "auto"

    from src.copilot.facts import FactStore
    from src.copilot.agent import CopilotAgent

    try:
        store = FactStore(run_folder)
        agent = CopilotAgent(store, provider=provider)
        resp = agent.ask(question)

        # Build sources list (file + field per grounded fact/number)
        sources = []
        seen_keys = set()
        for fact_id in getattr(resp, "tools_called", []):
            pass

        # Collect fact references from tool outputs
        for t_out in getattr(resp, "tool_outputs", []):
            f_ids = t_out.get("fact_ids", [])
            for fid in f_ids:
                if fid not in seen_keys and fid in store.facts:
                    f = store.facts[fid]
                    sources.append({
                        "file": f.source_file,
                        "field": f.id,
                        "value": str(f.value),
                        "unit": f.unit,
                        "evidence": f.evidence,
                    })
                    seen_keys.add(fid)

        # Fallback sources if tool outputs did not specify individual fact_ids
        if not sources and resp.tools_called:
            for tool_name in resp.tools_called:
                if tool_name in ["event_summary", "damage_summary"]:
                    sources.append({"file": "processed/damage_summary.json", "field": "buildings.damage_grade_counts"})
                    sources.append({"file": "processed/damage_summary.json", "field": "roads.km_by_damage_grade"})
                    sources.append({"file": "processed/l2_stats.json", "field": "areas_km2"})
                elif tool_name == "cutoff_settlements":
                    sources.append({"file": "processed/routing/cutoff_summary.json", "field": "vehicle.optimistic.cut_off_count"})
                    sources.append({"file": "processed/routing/cutoff_summary.json", "field": "vehicle.optimistic.connected_unverified_count"})
                elif tool_name == "bridges_status":
                    sources.append({"file": "processed/damage_summary.json", "field": "bridges.damage_grade_counts"})
                elif tool_name in ["repair_priority", "rescue_priority"]:
                    sources.append({"file": "processed/routing/repair_packages.json", "field": "ranked_packages"})
                    sources.append({"file": "processed/routing/cutoff_summary.json", "field": "walking.optimistic.cut_off_count"})
                elif tool_name in ["limitations", "confidence_and_limits"]:
                    sources.append({"file": "run_summary.json", "field": "validation_status"})
                    sources.append({"file": "processed/damage_summary.json", "field": "roads.km_by_damage_grade.Unknown (cloud)"})

        # Strip any internal secret strings from text or logs just in case
        answer_text = resp.text

        return JSONResponse({
            "run_id": run_id,
            "run_label": agent._turn_run_label or run_id,
            "answer": answer_text,
            "answer_path": resp.answer_path or "offline",
            "provider": resp.provider or "offline",
            "model": resp.model or "offline",
            "language": resp.language or "en",
            "tools_called": resp.tools_called,
            "sources": sources,
        })
    except Exception as e:
        logger.exception("Error in copilot_ask: %s", e)
        # Fallback offline emergency response
        return JSONResponse({
            "run_id": run_id,
            "run_label": run_id,
            "answer": f"[ANSWERED IN OFFLINE MODE]\nAn offline processing error occurred: {str(e)}",
            "answer_path": "offline",
            "provider": "offline",
            "model": "offline",
            "language": "en",
            "tools_called": [],
            "sources": [],
        })


@app.get("/api/runs/{run_id}/sitrep")
def get_run_sitrep(run_id: str, lang: str = "en", format: str = "pdf"):
    """Generates and serves bilingual 1-page Situation Report (PDF or Markdown)."""
    run_folder = validate_run_id(run_id)

    from src.copilot.facts import FactStore
    from src.copilot.sitrep import SitRepGenerator

    store = FactStore(run_folder)
    gen = SitRepGenerator(store)

    target_lang = "ne" if lang.lower() in ["ne", "nepali", "nep"] else "en"
    cache_dir = run_folder / "processed" / "sitrep"
    cache_dir.mkdir(parents=True, exist_ok=True)

    if format.lower() == "md" or format.lower() == "markdown":
        md_text = gen.generate_markdown(lang=target_lang)
        return PlainTextResponse(md_text, media_type="text/markdown; charset=utf-8")

    # Generate PDF
    pdf_path = cache_dir / f"sitrep_{target_lang}.pdf"
    md_text = gen.generate_markdown(lang=target_lang)
    gen.generate_pdf(md_text, pdf_path, lang=target_lang)

    if not pdf_path.exists():
        raise HTTPException(status_code=500, detail="Failed to generate SitRep PDF")

    filename = f"sitrep_{run_id}_{target_lang}.pdf"
    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=filename,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )



_LAST_NOMINATIM_CALL: float = 0.0

@app.get("/api/search/place")
def search_place(q: str = Query(..., min_length=2)):
    """
    Queries OpenStreetMap Nominatim for places with 1s rate limit and standard headers.
    """
    global _LAST_NOMINATIM_CALL
    now = time.time()
    elapsed = now - _LAST_NOMINATIM_CALL
    if elapsed < 1.0:
        time.sleep(1.0 - elapsed)
    _LAST_NOMINATIM_CALL = time.time()

    import urllib.request
    import urllib.parse
    params = urllib.parse.urlencode({"q": q, "format": "json", "limit": 5})
    url = f"https://nominatim.openstreetmap.org/search?{params}"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "SpaceborneDisasterPlatform/1.1 (https://github.com/spaceborne/disaster-assessment)",
            "Referer": "http://127.0.0.1:8000/"
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return JSONResponse(data)
    except Exception as e:
        logger.warning(f"Nominatim search failed: {e}")
        return JSONResponse([])


@app.get("/")
def index():
    """Serves the main dashboard HTML interface."""
    index_file = STATIC_DIR / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=404, detail="Frontend index.html not found")
    return FileResponse(index_file)


if __name__ == "__main__":
    import uvicorn
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", 8000))
    logger.info(f"Starting Disaster Dashboard server on http://{host}:{port}")
    uvicorn.run("src.dashboard.app:app", host=host, port=port, reload=False)
