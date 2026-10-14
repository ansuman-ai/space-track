"""Shared Naming & Validation Module for Disaster Assessment.

Single source of truth used across Dashboard and Copilot:
1. Settlement formatting: "Near <nearest named place> (<km> km)", NEVER "Unnamed settlement".
2. Run label: event name from run_summary / event_name.txt if set (e.g. "Event Name Year"),
   otherwise the dashboard's operational OSM label.
3. Validation metrics: reads processed/validation_status.json with provenance tracking.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def format_settlement_name(
    settlement: Dict[str, Any],
    include_coords: bool = False,
    include_access: bool = False,
) -> str:
    """Format settlement into a human-readable label.

    Rule: Never show 'Unnamed settlement' or raw cluster IDs.
    - If unnamed cluster with nearest place: 'Near <place> (<dist> km)'
    - If named place: clean place name
    - Optional coordinates: '(lat, lon)'
    - Optional access: '[access: helicopter/airdrop only]' for dual-severed locations
    """
    raw_name = str(settlement.get("name", "")).strip()
    coords = settlement.get("coordinates")
    if not coords and "geometry" in settlement:
        geom = settlement.get("geometry", {})
        if geom.get("type") == "Point" and len(geom.get("coordinates", [])) >= 2:
            coords = geom["coordinates"]
    if not coords and "lon" in settlement and "lat" in settlement:
        try:
            coords = [float(settlement["lon"]), float(settlement["lat"])]
        except Exception:
            pass

    coord_str = f"({coords[1]:.4f}, {coords[0]:.4f})" if coords and len(coords) >= 2 else ""

    # Priority 1: Extract nearest named place from pipeline raw_name
    # Pattern: "... (nearest named place: Bahun Danda (बाहुनडाँडा), 1.4 km)"
    main_label = ""
    if "nearest named place:" in raw_name.lower():
        sub = re.split(r"nearest named place:\s*", raw_name, flags=re.IGNORECASE)[1].rstrip(")")
        if "," in sub:
            p_name, p_dist = sub.rsplit(",", 1)
            p_name = p_name.strip()
            p_dist = p_dist.strip()
            if "km" in p_dist.lower():
                main_label = f"Near {p_name} ({p_dist})"
            else:
                main_label = f"Near {p_name} ({p_dist} km)"
        else:
            main_label = f"Near {sub.strip()}"

    # Priority 1b: Extract place from 'Cluster near <place> (ID ...)'
    elif re.match(r"^Cluster near\s+", raw_name, flags=re.IGNORECASE):
        m = re.match(r"^Cluster near\s+([A-Za-z0-9_.\u0900-\u097F\s]+?)(?:\s*\(ID\s*\d+\))?$", raw_name, flags=re.IGNORECASE)
        if m:
            main_label = f"Near {m.group(1).strip()}"

    # Priority 2: Settlement properties nearest_named_place & dist_to_named_place_km
    elif settlement.get("nearest_named_place"):
        place = str(settlement.get("nearest_named_place")).strip()
        dist = settlement.get("dist_to_named_place_km")
        if dist is not None:
            try:
                main_label = f"Near {place} ({float(dist):.1f} km)"
            except Exception:
                main_label = f"Near {place} ({dist} km)"
        else:
            main_label = f"Near {place}"

    # Priority 3: Genuine named settlements (not unnamed or raw node/cluster IDs)
    elif not raw_name.lower().startswith((
        "unnamed settlement", "cluster near", "cluster_", "cluster ", "place node/", "node/"
    )):
        # Strip cluster tags or IDs like [cluster_0] or (ID 12)
        clean = re.sub(r"\s*\[cluster_\w+\]", "", raw_name)
        clean = re.sub(r"\s*\(ID\s*\d+\)", "", clean)
        # Strip trailing parenthetical if not Devanagari
        if "(" in clean and not any("\u0900" <= c <= "\u097F" for c in clean):
            clean = clean.split("(")[0].strip()
        main_label = clean.strip() or "Settlement"

    # Priority 4: Fallback for unnamed settlements without nearest place tag
    if not main_label:
        osm_feats = settlement.get("osm_features_nearby", [])
        if osm_feats and isinstance(osm_feats, list):
            f_name = osm_feats[0].get("name") or osm_feats[0].get("admin_centre")
            if f_name:
                main_label = f"Near {str(f_name).strip()}"

    # Priority 5: Coordinate-based fallback (NEVER "Unnamed settlement")
    if not main_label:
        if coord_str:
            main_label = f"Settlement near {coord_str}"
        else:
            main_label = "Local Settlement"

    label = main_label
    if include_coords and coord_str and coord_str not in label:
        label = f"{label} {coord_str}".strip()

    if include_access:
        v_opt = settlement.get("vehicle_status_opt", "")
        w_opt = settlement.get("walking_status_opt", "")
        if v_opt in ["cut_off", "no_network_access"] and w_opt in ["cut_off", "no_network_access"]:
            label += " [access: helicopter/airdrop only]"

    return label


def derive_operational_run_label(run_folder: Path, summary: Optional[Dict[str, Any]] = None) -> str:
    """Derives operational label strictly from OSM tags:

    1. place in ['city', 'town'] inside unbuffered bbox.
    2. Features with admin_centre / municipality / is_in / population inside unbuffered bbox.
    3. place == 'village' inside unbuffered bbox ordered by number of buildings nearby.
    4. Supplement with nearest city/town from buffered area within 25km.
    5. Supplement with nearest villages/features from buffered area.
    No hardcoded place names.
    """
    if summary is None:
        summary_file = run_folder / "run_summary.json"
        if summary_file.exists():
            try:
                summary = json.loads(summary_file.read_text(encoding="utf-8"))
            except Exception:
                summary = {}
        else:
            summary = {}

    bbox = summary.get("bbox", [])
    if len(bbox) != 4:
        parts = run_folder.name.replace("_", " ").split()
        return " ".join([p.capitalize() for p in parts])

    cx = (bbox[0] + bbox[2]) / 2.0
    cy = (bbox[1] + bbox[3]) / 2.0
    date = summary.get("event_date", "")
    raw_regime = summary.get("terrain_regime") or ("flat_floodplain" if "assam" in run_folder.name.lower() else "steep_valley")
    regime_str = "Flat Floodplain" if raw_regime == "flat_floodplain" else "Steep Valley"

    settle_file = run_folder / "processed" / "routing" / "settlements.geojson"
    settle_pts = []
    if settle_file.exists():
        try:
            s_geo = json.loads(settle_file.read_text(encoding="utf-8"))
            for feat in s_geo.get("features", []):
                p = feat.get("properties", {})
                b = p.get("building_count", 0)
                c = feat.get("geometry", {}).get("coordinates", [])
                if len(c) >= 2:
                    settle_pts.append((c[0], c[1], b))
        except Exception:
            pass

    def evaluate_places(pfile: Path, max_dist: Optional[float] = None) -> List[Dict[str, Any]]:
        if not pfile.exists():
            return []
        items = []
        seen = set()
        try:
            d = json.loads(pfile.read_text(encoding="utf-8"))
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

    # Priority 4: Supplement from buffered city/town within 25km
    if len(top_candidates) < 2:
        t_buf = [x for x in buf_items if x["tier"] == 1 and x["name"] not in top_candidates]
        t_buf.sort(key=lambda x: x["dist"])
        top_candidates.extend([x["name"] for x in t_buf])

    # Priority 5: Supplement from buffered admin/villages by buildings
    if len(top_candidates) < 2:
        v_buf = [x for x in buf_items if x["name"] not in top_candidates]
        v_buf.sort(key=lambda x: (x["tier"], -x["bld_count"], x["dist"]))
        top_candidates.extend([x["name"] for x in v_buf])

    picked = top_candidates[:2]
    prefix = " / ".join(picked) if picked else run_folder.name.replace("_", " ").title()
    return f"{prefix} — {date} ({regime_str})"


def get_run_label(run_folder: Path, summary: Optional[Dict[str, Any]] = None) -> str:
    """Return the operational run label:

    Uses event_name from run_summary.json / event_name.txt / event_metadata.json if set
    (e.g. 'Event Name Year'), else the dashboard's operational OSM label.
    """
    if summary is None:
        summary_file = run_folder / "run_summary.json"
        if summary_file.exists():
            try:
                summary = json.loads(summary_file.read_text(encoding="utf-8"))
            except Exception:
                summary = {}
        else:
            summary = {}

    # 1. Event name from run_summary.json
    event_name = summary.get("event_name")

    # 2. Event name from event_name.txt
    if not event_name:
        txt_path = run_folder / "event_name.txt"
        if txt_path.exists():
            try:
                event_name = txt_path.read_text(encoding="utf-8").strip()
            except Exception:
                pass

    # 3. Event name from event_metadata.json
    if not event_name:
        meta_json_path = run_folder / "event_metadata.json"
        if meta_json_path.exists():
            try:
                ev_meta = json.loads(meta_json_path.read_text(encoding="utf-8"))
                event_name = ev_meta.get("event_name") or ev_meta.get("name")
            except Exception:
                pass

    if event_name:
        return event_name

    # Fallback to OSM operational label
    return derive_operational_run_label(run_folder, summary)


def get_validation_metrics(run_folder: Path, summary: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Reads validation metrics with file and field provenance.

    Copilot and dashboard both use this to guarantee identical quoted metrics.
    """
    if summary is None:
        summary_file = run_folder / "run_summary.json"
        if summary_file.exists():
            try:
                summary = json.loads(summary_file.read_text(encoding="utf-8"))
            except Exception:
                summary = {}
        else:
            summary = {}

    proc = run_folder / "processed"
    val_status_file = proc / "validation_status.json"

    if val_status_file.exists():
        try:
            val_meta = json.loads(val_status_file.read_text(encoding="utf-8"))
            validation_status = val_meta.get("validation_status", "not validated against an official map (practice run)")
            official_benchmark = val_meta.get("official_benchmark", "Copernicus EMS" if "validated on" in validation_status else "none")
            metrics = val_meta.get("metrics", {})
            source_file = val_meta.get("source_file", "processed/validation_status.json")
            source_field = val_meta.get("source_field", "validation_status")
            return {
                "validation_status": validation_status,
                "official_benchmark": official_benchmark,
                "metrics": metrics,
                "source_file": source_file,
                "source_field": source_field,
            }
        except Exception:
            pass

    # Only runs with their own validation output may show a validation claim; every other run is a practice run
    return {
        "validation_status": "not validated against an official map (practice run)",
        "official_benchmark": "none",
        "metrics": {"precision": None, "f1": None},
        "source_file": "processed/validation_status.json",
        "source_field": "validation_status",
    }
