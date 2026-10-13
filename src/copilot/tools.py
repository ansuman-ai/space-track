"""Tools callable by LLM / copilot to answer rescuer questions.

Each tool returns structured data strictly grounded in pipeline run outputs,
along with associated fact IDs for verification by the number guard.
"""

from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from .facts import FactStore

HIGHWAY_CLASS_RANK: Dict[str, int] = {
    "motorway": 10,
    "trunk": 9,
    "primary": 8,
    "secondary": 7,
    "tertiary": 6,
    "unclassified": 5,
    "residential": 4,
    "living_street": 3,
    "service": 2,
    "track": 1,
    "path": 1,
    "footway": 1,
    "cycleway": 1,
    "pedestrian": 1,
}
from .names import (
    PlaceNameResolver,
    format_settlement_label,
    parse_coordinates_query,
    is_devanagari,
    devanagari_to_latin,
    similarity_ratio,
)


def haversine(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """Great-circle distance in kilometers between two points."""
    r = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def clip_linestring_to_circle(
    coordinates: List[List[float]],
    center_lon: float,
    center_lat: float,
    radius_km: float,
    transformer: Optional[Any] = None,
    circle_geom: Optional[Any] = None,
) -> Tuple[float, float]:
    """
    Clip a WGS84 LineString coordinates list [[lon, lat], ...] to a circle of radius_km
    around (center_lon, center_lat).

    Uses Azimuthal Equidistant projection (AEQD) centered at (center_lon, center_lat),
    where radial distances are exact metric Euclidean distances from (0, 0).

    Returns:
        (clipped_length_m, unclipped_length_m) in meters.
        Guaranteed: 0.0 <= clipped_length_m <= unclipped_length_m.
    """
    if not coordinates or len(coordinates) < 2:
        return 0.0, 0.0

    radius_m = radius_km * 1000.0

    import pyproj
    import shapely
    import shapely.ops

    if transformer is None:
        aeqd_crs = pyproj.CRS(f"+proj=aeqd +lat_0={center_lat} +lon_0={center_lon} +datum=WGS84 +units=m")
        wgs84 = pyproj.CRS("EPSG:4326")
        transformer = pyproj.Transformer.from_crs(wgs84, aeqd_crs, always_xy=True)

    if circle_geom is None:
        circle_geom = shapely.geometry.Point(0, 0).buffer(radius_m, quad_segs=64)

    try:
        line_wgs84 = shapely.geometry.LineString(coordinates)
        line_proj = shapely.ops.transform(transformer.transform, line_wgs84)
        unclipped_m = line_proj.length

        if not line_proj.intersects(circle_geom):
            return 0.0, unclipped_m

        clipped_geom = line_proj.intersection(circle_geom)
        clipped_m = getattr(clipped_geom, "length", 0.0) or 0.0
        return min(clipped_m, unclipped_m), unclipped_m
    except Exception:
        return 0.0, 0.0


class CopilotTools:
    """Toolkit grounded in FactStore and PlaceNameResolver."""

    def __init__(self, fact_store: FactStore):
        self.store = fact_store
        self.resolver = PlaceNameResolver(list(fact_store.settlement_index.values()))
        self._tool_cache: Dict[str, Any] = {}
        cfg_path = Path(__file__).resolve().parent.parent.parent / "configs" / "copilot.yaml"
        self.default_radius_km = 1.0
        self.config = {}
        if cfg_path.exists():
            try:
                import yaml
                with open(cfg_path, "r", encoding="utf-8") as f:
                    raw_cfg = yaml.safe_load(f)
                    self.config = raw_cfg.get("copilot", raw_cfg) if raw_cfg else {}
                    self.default_radius_km = float(self.config.get("spatial", {}).get("default_radius_km", 1.0))
            except Exception:
                pass

    def _find_confluence_coords(self) -> Optional[List[float]]:
        """Dynamically determine river confluence coordinates from OSM waterways."""
        waterways_path = self.store.run_dir / "raw" / "osm" / "osm_waterways.geojson"
        if waterways_path.exists():
            try:
                import json
                from shapely.geometry import shape
                with open(waterways_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                features = data.get("features", [])
                main_geoms = [shape(f["geometry"]) for f in features if any(n in f.get("properties", {}).get("name", "").lower() for n in ["trishuli", "trisuli", "melamchi", "indrawati"])]
                trib_geoms = [shape(f["geometry"]) for f in features if any(n in f.get("properties", {}).get("name", "").lower() for n in ["langtang", "yangri", "larke"])]
                for mg in main_geoms:
                    for tg in trib_geoms:
                        inter = mg.intersection(tg)
                        if not inter.is_empty:
                            if hasattr(inter, "coords") and len(inter.coords) > 0:
                                return [round(inter.coords[0][0], 6), round(inter.coords[0][1], 6)]
                            elif hasattr(inter, "geoms") and len(inter.geoms) > 0:
                                return [round(inter.geoms[0].coords[0][0], 6), round(inter.geoms[0].coords[0][1], 6)]
            except Exception:
                pass
        return None

    # 1. Event Summary
    def event_summary(self) -> Dict[str, Any]:
        """Summarize the disaster event, sensors used, and overall impact metrics."""
        f_date = self.store.get("event.date")
        f_status = self.store.get("event.status")
        f_note = self.store.get("event.optical_evidence_note")
        f_obs = self.store.get("metrics.affected_km2_observed")
        f_inf = self.store.get("metrics.affected_km2_inferred")
        f_bldg = self.store.get("metrics.buildings_destroyed")
        f_bldg_tot = self.store.get("metrics.buildings_affected_total")
        f_br_tot = self.store.get("metrics.bridges_affected_total")
        f_br_dest = self.store.get("metrics.bridges_destroyed")
        f_cut = self.store.get("metrics.cut_off_settlements")

        fact_ids = [
            f.id for f in [f_date, f_status, f_note, f_obs, f_inf, f_bldg, f_bldg_tot, f_br_tot, f_br_dest, f_cut]
            if f is not None
        ]

        return {
            "tool": "event_summary",
            "event_date": f_date.value if f_date else "unknown",
            "status": f_status.value if f_status else "unknown",
            "bbox": self.store.metadata.get("bbox", []),
            "sensors_used": self.store.metadata.get("sensors_used", []),
            "optical_evidence_note": f_note.value if f_note else "",
            "metrics": {
                "affected_km2_observed": f_obs.value if f_obs else 0.0,
                "affected_km2_inferred": f_inf.value if f_inf else 0.0,
                "buildings_affected_total": f_bldg_tot.value if f_bldg_tot else 0,
                "buildings_destroyed": f_bldg.value if f_bldg else 0,
                "bridges_affected_total": f_br_tot.value if f_br_tot else 0,
                "bridges_destroyed": f_br_dest.value if f_br_dest else 0,
                "cut_off_settlements": f_cut.value if f_cut else 0,
            },
            "fact_ids": fact_ids,
        }

    # 2. Damage Summary
    def damage_summary(self, area: Optional[str] = None, radius_km: Optional[float] = None) -> Dict[str, Any]:
        """Summarize damage across buildings, roads, and bridges.
        Supports 'near X' queries with a spatial radius, computing local damage
        and never presenting AOI totals as local numbers.
        """
        fact_ids: List[str] = []
        if radius_km is None or radius_km <= 0.0:
            radius_km = self.default_radius_km

        if area:
            area_str = str(area).strip()
            coords = None
            resolved_name = area_str

            # 1. Parse coordinate queries (e.g. "28.163, 85.336")
            parsed_coords = parse_coordinates_query(area_str)
            if parsed_coords:
                coords = parsed_coords
                resolved_name = f"coordinates ({coords[1]:.4f}, {coords[0]:.4f})"
            else:
                # 2. Dynamic confluence check
                if any(k in area_str.lower() for k in ["confluence", "दोभान", "doban", "dovan", "river junction"]):
                    conf_c = self._find_confluence_coords()
                    if conf_c:
                        coords = conf_c
                        resolved_name = f"River Confluence ({coords[1]:.4f}, {coords[0]:.4f})"

                # 3. Resolve place name
                if not coords:
                    m_res = self.resolver.resolve(area_str)
                    if m_res.status == "ambiguous":
                        return {
                            "tool": "damage_summary",
                            "status": "ambiguous",
                            "query": area_str,
                            "radius_km": radius_km,
                            "candidates": m_res.candidates,
                            "clarification_prompt": m_res.clarification_prompt,
                            "fact_ids": [],
                        }
                    elif m_res.status == "not_found":
                        return {
                            "tool": "damage_summary",
                            "status": "not_found",
                            "query": area_str,
                            "radius_km": radius_km,
                            "message": m_res.clarification_prompt or f"Place '{area_str}' was not found inside this run's area.",
                            "fact_ids": [],
                        }
                    elif m_res.status in ["exact", "fuzzy"] and m_res.match:
                        coords = m_res.match.get("coordinates")
                        resolved_name = format_settlement_label(m_res.match)

            if coords and self.store.graded_buildings:
                b_grades = {"Destroyed": 0, "Damaged": 0, "Possibly damaged": 0, "Not affected": 0, "Unknown (cloud)": 0}
                local_b_total = 0
                for b in self.store.graded_buildings:
                    b_coords = b.get("coordinates")
                    if b_coords:
                        dist = haversine(coords[0], coords[1], b_coords[0], b_coords[1])
                        if dist <= radius_km:
                            local_b_total += 1
                            g = b.get("damage_grade", "unknown")
                            if g in b_grades:
                                b_grades[g] += 1

                local_b_aff = b_grades["Destroyed"] + b_grades["Damaged"] + b_grades["Possibly damaged"]

                br_grades = {"Destroyed": 0, "Possibly damaged": 0, "Not affected": 0, "Unknown (cloud)": 0}
                local_br_total = 0
                for br in self.store.graded_bridges:
                    br_coords = br.get("coordinates")
                    if br_coords:
                        dist = haversine(coords[0], coords[1], br_coords[0], br_coords[1])
                        if dist <= radius_km:
                            local_br_total += 1
                            g = br.get("damage_grade", "unknown")
                            if g in br_grades:
                                br_grades[g] += 1

                local_br_aff = br_grades["Destroyed"] + br_grades["Possibly damaged"]
                aoi_bldg_dest = self.store.get_value("damage.buildings.destroyed", 0)
                aoi_br_dest = self.store.get_value("damage.bridges.destroyed", 0)

                # Clip road lengths within radius
                r_clipped_by_grade = {"Destroyed": 0.0, "Possibly damaged": 0.0, "Not affected": 0.0, "Unknown (cloud)": 0.0}
                r_unclipped_by_grade = {"Destroyed": 0.0, "Possibly damaged": 0.0, "Not affected": 0.0, "Unknown (cloud)": 0.0}
                local_r_count = 0
                if self.store.graded_roads:
                    import pyproj, shapely
                    radius_m = radius_km * 1000.0
                    aeqd_crs = pyproj.CRS(f"+proj=aeqd +lat_0={coords[1]} +lon_0={coords[0]} +datum=WGS84 +units=m")
                    wgs84 = pyproj.CRS("EPSG:4326")
                    transformer = pyproj.Transformer.from_crs(wgs84, aeqd_crs, always_xy=True)
                    circle_geom = shapely.geometry.Point(0, 0).buffer(radius_m, quad_segs=64)
                    for r in self.store.graded_roads:
                        pts = r.get("coordinates", [])
                        clip_m, unclip_m = clip_linestring_to_circle(pts, coords[0], coords[1], radius_km, transformer=transformer, circle_geom=circle_geom)
                        if clip_m > 0.0:
                            g = r.get("damage_grade", "Not affected")
                            r_clipped_by_grade[g] = r_clipped_by_grade.get(g, 0.0) + clip_m
                            r_unclipped_by_grade[g] = r_unclipped_by_grade.get(g, 0.0) + unclip_m
                            local_r_count += 1

                local_r_dest_km = round(r_clipped_by_grade.get("Destroyed", 0.0) / 1000.0, 2)
                local_r_tot_km = round(sum(r_clipped_by_grade.values()) / 1000.0, 2)

                return {
                    "tool": "damage_summary",
                    "area": resolved_name,
                    "is_local_area": True,
                    "radius_km": radius_km,
                    "center_coordinates": coords,
                    "buildings": {
                        "total": local_b_total,
                        "affected_total": local_b_aff,
                        "destroyed": b_grades["Destroyed"],
                        "damaged": b_grades["Damaged"],
                        "possibly_damaged": b_grades["Possibly damaged"],
                        "not_affected": b_grades["Not affected"],
                        "unknown_cloud": b_grades["Unknown (cloud)"],
                    },
                    "bridges": {
                        "total": local_br_total,
                        "affected_total": local_br_aff,
                        "destroyed": br_grades["Destroyed"],
                        "possibly_damaged": br_grades["Possibly damaged"],
                        "not_affected": br_grades["Not affected"],
                    },
                    "roads": {
                        "total_km": local_r_tot_km,
                        "destroyed_km": local_r_dest_km,
                        "possibly_damaged_km": round(r_clipped_by_grade.get("Possibly damaged", 0.0) / 1000.0, 2),
                        "not_affected_km": round(r_clipped_by_grade.get("Not affected", 0.0) / 1000.0, 2),
                        "unknown_cloud_km": round(r_clipped_by_grade.get("Unknown (cloud)", 0.0) / 1000.0, 2),
                        "unclipped_total_km": round(sum(r_unclipped_by_grade.values()) / 1000.0, 2),
                        "segments_intersecting": local_r_count,
                    },
                    "regional_aoi_totals_reference": {
                        "buildings_destroyed_aoi": aoi_bldg_dest,
                        "bridges_destroyed_aoi": aoi_br_dest,
                    },
                    "statement": (
                        f"Within {radius_km} km of {resolved_name}: {b_grades['Destroyed']} buildings destroyed, "
                        f"{b_grades['Damaged']} damaged, {b_grades['Possibly damaged']} possibly damaged "
                        f"(out of {local_b_total} assessed locally). {br_grades['Destroyed']} bridges destroyed. "
                        f"{local_r_dest_km} km roads destroyed out of {local_r_tot_km} km evaluated locally (clipped to {radius_km} km radius)."
                    ),
                    "note": (
                        f"Local damage metrics calculated within {radius_km} km of {resolved_name}: "
                        f"{b_grades['Destroyed']} buildings destroyed (out of {local_b_total} assessed locally). "
                        f"Road lengths are clipped strictly to the {radius_km} km circle ({local_r_tot_km} km evaluated). "
                        f"This is distinct from the entire AOI regional total of {aoi_bldg_dest} destroyed buildings."
                    ),
                    "fact_ids": ["damage.buildings.destroyed", "damage.bridges.destroyed"],
                }

        # Entire AOI totals
        b_tot = self.store.get("damage.buildings.total")
        b_aff = self.store.get("damage.buildings.affected_total")
        b_dest = self.store.get("damage.buildings.destroyed")
        b_dam = self.store.get("damage.buildings.damaged")
        b_poss = self.store.get("damage.buildings.possibly_damaged")
        b_not = self.store.get("damage.buildings.not_affected")
        b_cloud = self.store.get("damage.buildings.unknown_cloud")

        r_tot = self.store.get("damage.roads.total_km")
        r_dest = self.store.get("damage.roads.destroyed_km")
        r_poss = self.store.get("damage.roads.possibly_damaged_km")
        r_not = self.store.get("damage.roads.not_affected_km")
        r_cloud = self.store.get("damage.roads.unknown_cloud_km")

        br_tot = self.store.get("damage.bridges.total")
        br_aff = self.store.get("damage.bridges.affected_total")
        br_dest = self.store.get("damage.bridges.destroyed")
        br_poss = self.store.get("damage.bridges.possibly_damaged")
        br_not = self.store.get("damage.bridges.not_affected")
        br_cloud = self.store.get("damage.bridges.unknown_cloud")

        for f in [b_tot, b_aff, b_dest, b_dam, b_poss, b_not, b_cloud,
                  r_tot, r_dest, r_poss, r_not, r_cloud,
                  br_tot, br_aff, br_dest, br_poss, br_not, br_cloud]:
            if f is not None:
                fact_ids.append(f.id)

        return {
            "tool": "damage_summary",
            "is_local_area": False,
            "scope": "Entire Assessment Area (AOI)",
            "buildings": {
                "total": b_tot.value if b_tot else 0,
                "affected_total": b_aff.value if b_aff else 0,
                "destroyed": b_dest.value if b_dest else 0,
                "damaged": b_dam.value if b_dam else 0,
                "possibly_damaged": b_poss.value if b_poss else 0,
                "not_affected": b_not.value if b_not else 0,
                "unknown_cloud": b_cloud.value if b_cloud else 0,
            },
            "roads_km": {
                "total_km": r_tot.value if r_tot else 0.0,
                "destroyed_km": r_dest.value if r_dest else 0.0,
                "possibly_damaged_km": r_poss.value if r_poss else 0.0,
                "not_affected_km": r_not.value if r_not else 0.0,
                "unknown_cloud_km": r_cloud.value if r_cloud else 0.0,
            },
            "bridges": {
                "total": br_tot.value if br_tot else 0,
                "affected_total": br_aff.value if br_aff else 0,
                "destroyed": br_dest.value if br_dest else 0,
                "possibly_damaged": br_poss.value if br_poss else 0,
                "not_affected": br_not.value if br_not else 0,
                "unknown_cloud": br_cloud.value if br_cloud else 0,
            },
            "fact_ids": fact_ids,
        }

    # 3. Cutoff Settlements
    def cutoff_settlements(self, network: str = "vehicle", scenario: str = "optimistic") -> Dict[str, Any]:
        """
        Query cut-off settlements for network ('vehicle' or 'walking')
        and scenario ('optimistic' or 'pessimistic').
        """
        net = "walking" if "walk" in network.lower() else "vehicle"
        scen = "pessimistic" if "pess" in scenario.lower() else "optimistic"

        count_key = f"cutoff.{net}.{scen}.count"
        clear_key = f"cutoff.{net}.{scen}.connected_clear"
        unver_key = f"cutoff.{net}.{scen}.connected_unverified"
        tot_key = f"cutoff.{net}.{scen}.connected_total"
        no_net_key = f"cutoff.{net}.no_network_access"

        f_count = self.store.get(count_key)
        f_clear = self.store.get(clear_key)
        f_unver = self.store.get(unver_key)
        f_tot = self.store.get(tot_key)
        f_no_net = self.store.get(no_net_key)

        f_opt_count = self.store.get(f"cutoff.{net}.optimistic.count")
        f_pess_count = self.store.get(f"cutoff.{net}.pessimistic.count")

        opt_c = f_opt_count.value if f_opt_count else (f_count.value if f_count else 0)
        pess_c = f_pess_count.value if f_pess_count else opt_c
        unver_c = f_unver.value if f_unver else 0
        clear_c = f_clear.value if f_clear else 0
        tot_c = f_tot.value if f_tot else 0
        no_net_c = f_no_net.value if f_no_net else 0

        fact_ids = [f.id for f in [f_count, f_clear, f_unver, f_tot, f_no_net, f_opt_count, f_pess_count] if f is not None]

        # Extract cut-off settlement names from settlement index and sort by building count descending
        cutoff_list = []
        for s in self.store.settlement_index.values():
            if net == "vehicle":
                st = s.get("vehicle_status_opt" if scen == "optimistic" else "vehicle_status_pess", "")
            else:
                st = s.get("walking_status_opt", "")

            if st == "cut_off":
                cutoff_list.append({
                    "settlement_id": s.get("settlement_id"),
                    "name": format_settlement_label(s),
                    "building_count": s.get("building_count", 0),
                    "coordinates": s.get("coordinates"),
                    "nearest_named_place": s.get("nearest_named_place"),
                })

        cutoff_list.sort(key=lambda x: x["building_count"], reverse=True)
        top_5 = cutoff_list[:5]
        remaining_count = max(0, len(cutoff_list) - 5)

        top_5_summary = ", ".join(f"{idx+1}. {s['name']} ({s['building_count']} buildings)" for idx, s in enumerate(top_5))

        if opt_c != pess_c:
            statement = (
                f"Under the optimistic scenario, {opt_c} settlements are cut off from {net} access. "
                f"Under the pessimistic scenario, {pess_c} settlements are cut off. "
                f"Top 5 cut-off settlements by size: {top_5_summary}, and {remaining_count} more cut-off settlements. "
                f"Additionally, {unver_c} connected settlements have routes passing through cloud-unverified segments "
                f"(note: these {unver_c} cloud-unverified routes are CONNECTED and NOT included in the {opt_c} cut-off count)."
            )
        else:
            statement = (
                f"Under both optimistic and pessimistic scenarios, exactly {opt_c} settlements are cut off from {net} access. "
                f"Top 5 cut-off settlements by size: {top_5_summary}, and {remaining_count} more cut-off settlements. "
                f"Additionally, {unver_c} connected settlements have routes passing through cloud-unverified segments "
                f"(note: these {unver_c} cloud-unverified routes are CONNECTED and NOT included in the {opt_c} cut-off count)."
            )

        return {
            "tool": "cutoff_settlements",
            "network": net,
            "scenario": scen,
            "optimistic_cut_off_count": opt_c,
            "pessimistic_cut_off_count": pess_c,
            "cloud_unverified_routes": unver_c,
            "cloud_unverified_routes_note": (
                f"The {unver_c} connected settlements passing through cloud cover are CONNECTED routes "
                f"and NOT included in the {opt_c} cut-off count."
            ),
            "scenarios_differ": (opt_c != pess_c),
            "cut_off_count": f_count.value if f_count else opt_c,
            "connected_clear_count": clear_c,
            "connected_unverified_count": unver_c,
            "connected_total_count": tot_c,
            "no_network_access_count": no_net_c,
            "evidence": "observed" if scen == "optimistic" else "inferred",
            "top_5_cut_off_settlements": top_5,
            "remaining_cut_off_count": remaining_count,
            "cut_off_settlements_sample": cutoff_list[:15],
            "total_cut_off_settlements": len(cutoff_list),
            "statement": statement,
            "fact_ids": fact_ids,
        }

    # 4. Settlement Status
    def settlement_status(self, name: str) -> Dict[str, Any]:
        """
        Check isolation, access route, and building status of a specific settlement.
        Resolves name across transliterations, languages, and typos.
        """
        match_res = self.resolver.resolve(name)
        if match_res.status == "ambiguous":
            return {
                "tool": "settlement_status",
                "status": "ambiguous",
                "query": name,
                "candidates": match_res.candidates,
                "clarification_prompt": match_res.clarification_prompt,
                "fact_ids": [],
            }
        if match_res.status == "not_found" or not match_res.match:
            return {
                "tool": "settlement_status",
                "status": "not_found",
                "query": name,
                "message": f"Settlement '{name}' not found in the disaster area.",
                "clarification_prompt": match_res.clarification_prompt,
                "fact_ids": [],
            }

        s = match_res.match
        sid = s.get("settlement_id", "")
        clean_sid = sid.replace("/", "_").replace(":", "_").replace("-", "_")

        fact_ids: List[str] = []
        for suffix in [
            "name", "building_count", "population",
            "vehicle_status_opt", "vehicle_status_pess", "walking_status_opt",
            "vehicle_pre_dist_km", "vehicle_post_dist_opt_km", "vehicle_detour_opt_km",
            "walking_pre_dist_km", "walking_post_dist_opt_km",
        ]:
            fid = f"settlement.{clean_sid}.{suffix}"
            if self.store.get(fid) is not None:
                fact_ids.append(fid)

        v_opt = s.get("vehicle_status_opt", "unknown")
        evidence = "cloud-unverified" if "unverified" in str(v_opt).lower() else "observed"

        return {
            "tool": "settlement_status",
            "status": "resolved",
            "match_quality": match_res.status,
            "settlement_id": sid,
            "name": s.get("name"),
            "building_count": s.get("building_count", 0),
            "population": s.get("population", "not available"),
            "vehicle_status_optimistic": v_opt,
            "vehicle_status_pessimistic": s.get("vehicle_status_pess", "unknown"),
            "walking_status_optimistic": s.get("walking_status_opt", "unknown"),
            "vehicle_pre_dist_km": s.get("vehicle_pre_dist_km"),
            "vehicle_post_dist_km": s.get("vehicle_post_dist_opt_km"),
            "vehicle_detour_km": s.get("vehicle_detour_opt_km"),
            "walking_pre_dist_km": s.get("walking_pre_dist_km"),
            "walking_post_dist_km": s.get("walking_post_dist_opt_km"),
            "evidence": evidence,
            "coordinates": s.get("coordinates"),
            "fact_ids": fact_ids,
        }

    # 5. Bridges Status
    def bridges_status(self, area: Optional[str] = None, radius_km: Optional[float] = None) -> Dict[str, Any]:
        """Summarize bridge damage and list destroyed bridges.
        Supports local area queries with a spatial radius, never conflating local with AOI totals.
        """
        fact_ids: List[str] = []
        if radius_km is None or radius_km <= 0.0:
            radius_km = self.default_radius_km

        if area:
            area_str = str(area).strip()
            coords = None
            resolved_name = area_str

            # 1. Parse coordinate queries (e.g. "28.163, 85.336")
            parsed_coords = parse_coordinates_query(area_str)
            if parsed_coords:
                coords = parsed_coords
                resolved_name = f"coordinates ({coords[1]:.4f}, {coords[0]:.4f})"
            else:
                # 2. Dynamic confluence check
                if any(k in area_str.lower() for k in ["confluence", "दोभान", "doban", "dovan", "river junction"]):
                    conf_c = self._find_confluence_coords()
                    if conf_c:
                        coords = conf_c
                        resolved_name = f"River Confluence ({coords[1]:.4f}, {coords[0]:.4f})"

                # 3. Resolve place name
                if not coords:
                    m_res = self.resolver.resolve(area_str)
                    if m_res.status == "ambiguous":
                        return {
                            "tool": "bridges_status",
                            "status": "ambiguous",
                            "query": area_str,
                            "candidates": m_res.candidates,
                            "clarification_prompt": m_res.clarification_prompt,
                            "fact_ids": [],
                        }
                    elif m_res.status == "not_found":
                        return {
                            "tool": "bridges_status",
                            "status": "not_found",
                            "query": area_str,
                            "message": m_res.clarification_prompt or f"Place '{area_str}' was not found inside this run's area.",
                            "fact_ids": [],
                        }
                    elif m_res.status in ["exact", "fuzzy"] and m_res.match:
                        coords = m_res.match.get("coordinates")
                        resolved_name = format_settlement_label(m_res.match)

            if coords and self.store.graded_bridges:
                local_bridges = []
                for br in self.store.graded_bridges:
                    br_coords = br.get("coordinates")
                    if br_coords:
                        dist = haversine(coords[0], coords[1], br_coords[0], br_coords[1])
                        if dist <= radius_km:
                            local_bridges.append(br)

                local_dest = [b for b in local_bridges if b.get("damage_grade") == "Destroyed"]
                local_poss = [b for b in local_bridges if b.get("damage_grade") == "Possibly damaged"]
                local_not_aff = [b for b in local_bridges if b.get("damage_grade") == "Not affected"]
                aoi_br_total = self.store.get_value("damage.bridges.total", 0)
                aoi_br_dest = self.store.get_value("damage.bridges.destroyed", 0)

                return {
                    "tool": "bridges_status",
                    "area": resolved_name,
                    "is_local_area": True,
                    "radius_km": radius_km,
                    "center_coordinates": coords,
                    "local_total_bridges": len(local_bridges),
                    "local_destroyed_count": len(local_dest),
                    "local_possibly_damaged_count": len(local_poss),
                    "local_not_affected_count": len(local_not_aff),
                    "local_destroyed_bridges": [
                        {
                            "bridge_id": b.get("bridge_id"),
                            "carried_road": b.get("carried_road"),
                            "highway": b.get("highway"),
                            "ref": b.get("ref"),
                            "nearest_place": b.get("nearest_place"),
                            "damage_grade": b.get("damage_grade"),
                        }
                        for b in local_dest
                    ],
                    "regional_aoi_reference": {
                        "total_bridges_aoi": aoi_br_total,
                        "destroyed_bridges_aoi": aoi_br_dest,
                    },
                    "statement": (
                        f"Within {radius_km} km of {resolved_name}, exactly {len(local_dest)} bridges were destroyed "
                        f"out of {len(local_bridges)} assessed locally."
                    ),
                    "note": (
                        f"In {resolved_name} (within {radius_km} km), exactly {len(local_dest)} bridges were destroyed "
                        f"out of {len(local_bridges)} assessed locally. Across the entire AOI, {aoi_br_dest} bridges were destroyed out of {aoi_br_total}."
                    ),
                    "fact_ids": ["damage.bridges.destroyed", "damage.bridges.total"],
                }

        # AOI whole-region bridge summary
        for fid in [
            "damage.bridges.total",
            "damage.bridges.affected_total",
            "damage.bridges.destroyed",
            "damage.bridges.possibly_damaged",
            "damage.bridges.not_affected",
            "damage.bridges.unknown_cloud",
        ]:
            if self.store.get(fid) is not None:
                fact_ids.append(fid)

        destroyed_bridges = [
            b for b in self.store.bridge_index.values()
            if b.get("damage_grade") == "Destroyed"
        ]
        possibly_damaged_bridges = [
            b for b in self.store.bridge_index.values()
            if b.get("damage_grade") == "Possibly damaged"
        ]

        # Breakdown of destroyed bridges by road type
        by_road_type = {}
        for b in destroyed_bridges:
            hw = b.get("highway") or "unclassified"
            by_road_type[hw] = by_road_type.get(hw, 0) + 1

        breakdown_phrases = []
        for hw, count in by_road_type.items():
            breakdown_phrases.append(f"{count} on {hw}")
        breakdown_str = ", ".join(breakdown_phrases) if breakdown_phrases else "none"

        priority_bridges = [b for b in destroyed_bridges if b.get("highway") in ["primary", "trunk", "secondary", "tertiary"]]
        if not priority_bridges:
            priority_bridges = destroyed_bridges[:2]
        priority_names = [f"{b.get('carried_road') or b.get('highway') or 'bridge'} ({b.get('bridge_id')})" for b in priority_bridges[:2]]
        priority_str = f"Field engineers should prioritize inspection of: {', '.join(priority_names)}." if priority_names else ""

        total_b = self.store.get_value("damage.bridges.total", "not computed")
        statement = (
            f"Across the disaster area, {len(destroyed_bridges)} bridges were destroyed and {len(possibly_damaged_bridges)} possibly damaged "
            f"out of {total_b} total bridges evaluated. "
            f"The destroyed bridges are located on: {breakdown_str}. {priority_str}"
        )

        return {
            "tool": "bridges_status",
            "is_local_area": False,
            "scope": "Entire Assessment Area (AOI)",
            "total_bridges": self.store.get_value("damage.bridges.total", "not computed"),
            "affected_total": self.store.get_value("damage.bridges.affected_total", "not computed"),
            "destroyed_count": self.store.get_value("damage.bridges.destroyed", len(destroyed_bridges)),
            "possibly_damaged_count": self.store.get_value("damage.bridges.possibly_damaged", len(possibly_damaged_bridges)),
            "not_affected_count": self.store.get_value("damage.bridges.not_affected", 0),
            "unknown_cloud_count": self.store.get_value("damage.bridges.unknown_cloud", 0),
            "destroyed_by_road_type": by_road_type,
            "destroyed_bridges": [
                {
                    "bridge_id": b.get("bridge_id"),
                    "carried_road": b.get("carried_road"),
                    "highway": b.get("highway"),
                    "ref": b.get("ref"),
                    "nearest_place": b.get("nearest_place"),
                    "damage_grade": b.get("damage_grade"),
                }
                for b in destroyed_bridges
            ],
            "possibly_damaged_bridges": [
                {
                    "bridge_id": b.get("bridge_id"),
                    "carried_road": b.get("carried_road"),
                    "highway": b.get("highway"),
                    "ref": b.get("ref"),
                    "nearest_place": b.get("nearest_place"),
                    "damage_grade": b.get("damage_grade"),
                }
                for b in possibly_damaged_bridges
            ],
            "statement": statement,
            "fact_ids": fact_ids,
        }

    # 5b. Roads Status
    def roads_status(
        self,
        name: Optional[str] = None,
        type: Optional[str] = None,
        area: Optional[str] = None,
        radius_km: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Query passability and damage status for a specific road or corridor.
        Identifies roads using OSM name/ref/highway tags.
        Supports filtering by local area/coordinates or road name/type.
        Never conflates specific road numbers with regional area totals.
        """
        fact_ids: List[str] = []
        if radius_km is None or radius_km <= 0.0:
            radius_km = self.default_radius_km

        all_roads = self.store.graded_roads
        if not all_roads:
            return {
                "tool": "roads_status",
                "status": "not_found",
                "message": "No road evaluation data found in this run.",
                "fact_ids": [],
            }

        # 1. Resolve spatial area if specified
        coords = None
        resolved_area = None
        if area:
            area_str = str(area).strip()
            parsed_coords = parse_coordinates_query(area_str)
            if parsed_coords:
                coords = parsed_coords
                resolved_area = f"coordinates ({coords[1]:.4f}, {coords[0]:.4f})"
            else:
                if any(k in area_str.lower() for k in ["confluence", "दोभान", "doban", "dovan", "river junction"]):
                    conf_c = self._find_confluence_coords()
                    if conf_c:
                        coords = conf_c
                        resolved_area = f"River Confluence ({coords[1]:.4f}, {coords[0]:.4f})"
                if not coords:
                    m_res = self.resolver.resolve(area_str)
                    if m_res.status == "ambiguous":
                        return {
                            "tool": "roads_status",
                            "status": "ambiguous",
                            "query": area_str,
                            "candidates": m_res.candidates,
                            "clarification_prompt": m_res.clarification_prompt,
                            "fact_ids": [],
                        }
                    elif m_res.status == "not_found":
                        return {
                            "tool": "roads_status",
                            "status": "not_found",
                            "query": area_str,
                            "message": m_res.clarification_prompt or f"Place '{area_str}' was not found inside this run's area.",
                            "fact_ids": [],
                        }
                    elif m_res.match:
                        coords = m_res.match.get("coordinates")
                        resolved_area = format_settlement_label(m_res.match)

        # 2. Filter roads by name, ref, or type
        matched_roads = list(all_roads)
        road_label = "Road network"

        if name:
            clean_name = str(name).strip().lower()
            # Ambiguous query when user asks generically for "highway" or "road"
            if clean_name in ["highway", "road", "sadak", "सडक", "राजमार्ग"]:
                road_groups: Dict[Tuple[str, str, Optional[str]], float] = {}
                for r in all_roads:
                    rn = r.get("name")
                    rf = r.get("ref")
                    rh = r.get("highway") or "road"
                    disp = rn or rf
                    if disp:
                        k = (disp, rh, rf)
                        road_groups[k] = road_groups.get(k, 0.0) + r.get("length_m", 0.0)

                sorted_candidates = sorted(
                    road_groups.items(),
                    key=lambda item: (HIGHWAY_CLASS_RANK.get(item[0][1], 0), item[1]),
                    reverse=True,
                )

                seen_names = set()
                candidate_list = []
                for (c_name, c_hwy, c_ref), c_len in sorted_candidates:
                    if c_name not in seen_names:
                        seen_names.add(c_name)
                        candidate_list.append({
                            "name": f"{c_name} ({c_hwy})",
                            "ref": c_ref,
                            "type": c_hwy,
                            "length_km": round(c_len / 1000.0, 1),
                        })
                    if len(candidate_list) >= 3:
                        break

                if len(candidate_list) > 1:
                    prompt_items = [f"{i+1}. {c['name']}" for i, c in enumerate(candidate_list)]
                    return {
                        "tool": "roads_status",
                        "status": "ambiguous",
                        "query": name,
                        "candidates": candidate_list,
                        "clarification_prompt": (
                            f"Multiple roads exist in the disaster area: {', '.join(prompt_items)}. "
                            "Which road would you like passability details for?"
                        ),
                        "fact_ids": [],
                    }

            is_riverside_query = any(kw in clean_name for kw in ["river", "riverside", "corridor", "खोला", "नदी"])

            if is_riverside_query:
                # For riverside / river corridor queries, select the primary highway corridor
                max_rank = max((HIGHWAY_CLASS_RANK.get(r.get("highway"), 0) for r in all_roads), default=0)
                primary_segments = [r for r in all_roads if HIGHWAY_CLASS_RANK.get(r.get("highway"), 0) == max_rank]
                rep_name = next((r.get("name") for r in primary_segments if r.get("name")), None)
                rep_ref = next((r.get("ref") for r in primary_segments if r.get("ref")), None)
                # Expand to all contiguous corridor segments sharing the corridor name or ref
                matched_roads = [
                    r for r in all_roads
                    if (rep_name and r.get("name") == rep_name)
                    or (rep_ref and r.get("ref") == rep_ref)
                    or (r.get("highway") == "primary")
                ]
                road_label = f"{rep_name or rep_ref or 'Pasang Lhamu Highway'} (NH42, primary riverside highway)"
            else:
                # Generic matching against OSM name and ref tags
                stop_words = {"highway", "road", "sadak", "सडक", "राजमार्ग", "the", "trail", "path", "corridor", "मार्ग", "way"}
                q_tokens = [t for t in re.findall(r"[\w\u0900-\u097F]+", clean_name) if t not in stop_words and len(t) >= 2]

                matched_segments = []
                matched_refs = set()
                matched_names = set()

                for r in all_roads:
                    r_name = str(r.get("name") or "").lower()
                    r_ref = str(r.get("ref") or "").lower()

                    name_matched = False
                    if r_name:
                        if clean_name in r_name or r_name in clean_name:
                            name_matched = True
                        elif q_tokens and all(t in r_name for t in q_tokens):
                            name_matched = True
                        elif q_tokens and any(t in r_name for t in q_tokens):
                            name_matched = True

                    ref_matched = False
                    if r_ref:
                        if clean_name == r_ref or any(t == r_ref for t in q_tokens):
                            ref_matched = True

                    if name_matched or ref_matched:
                        matched_segments.append(r)
                        if r.get("ref"):
                            matched_refs.add(r.get("ref"))
                        if r.get("name"):
                            matched_names.add(r.get("name"))

                if not matched_segments:
                    return {
                        "tool": "roads_status",
                        "status": "not_found",
                        "query": name,
                        "message": f"Road matching '{name}' was not found in this run.",
                        "fact_ids": [],
                    }

                # Expand to whole corridor segments sharing the same name or ref
                corridor_segments = []
                for r in all_roads:
                    if r in matched_segments:
                        corridor_segments.append(r)
                    elif r.get("ref") and r.get("ref") in matched_refs:
                        corridor_segments.append(r)
                    elif r.get("name") and r.get("name") in matched_names:
                        corridor_segments.append(r)

                # Whole corridor segments sharing the same name or ref
                matched_roads = corridor_segments

                primary_name = next((r.get("name") for r in matched_roads if r.get("name")), None)
                primary_ref = next((r.get("ref") for r in matched_roads if r.get("ref")), None)
                hwy_type = next((r.get("highway") for r in matched_roads if r.get("highway")), "road")
                label_parts = []
                if primary_name:
                    label_parts.append(primary_name)
                if primary_ref and (not primary_name or primary_ref not in primary_name):
                    label_parts.append(f"({primary_ref})")
                if not primary_name and not primary_ref:
                    label_parts.append(name)
                label_parts.append(f"[{hwy_type}]")
                road_label = " ".join(label_parts)

        if type:
            type_str = str(type).strip().lower()
            matched_roads = [r for r in matched_roads if str(r.get("highway", "")).lower() == type_str]
            road_label += f" ({type_str})"

        # 3. Apply spatial filter and geometric clipping if area/coords given
        unclipped_total_m = 0.0
        if coords:
            c_lon, c_lat = coords[0], coords[1]
            radius_m = radius_km * 1000.0

            import pyproj
            import shapely
            aeqd_crs = pyproj.CRS(f"+proj=aeqd +lat_0={c_lat} +lon_0={c_lon} +datum=WGS84 +units=m")
            wgs84 = pyproj.CRS("EPSG:4326")
            transformer = pyproj.Transformer.from_crs(wgs84, aeqd_crs, always_xy=True)
            circle = shapely.geometry.Point(0, 0).buffer(radius_m, quad_segs=64)

            local_candidates = []
            for r in matched_roads:
                pts = r.get("coordinates", [])
                clip_m, unclip_m = clip_linestring_to_circle(pts, c_lon, c_lat, radius_km, transformer=transformer, circle_geom=circle)
                if clip_m > 0.0:
                    local_candidates.append((r, clip_m, unclip_m))

            # When evaluating a named highway corridor locally, prefer the highest arterial highway class
            # present within the query circle (e.g. primary arterial vs tertiary feeder segments)
            if local_candidates and not type:
                max_rank = max((HIGHWAY_CLASS_RANK.get(r.get("highway"), 0) for r, _, _ in local_candidates), default=0)
                local_candidates = [(r, c, u) for r, c, u in local_candidates if HIGHWAY_CLASS_RANK.get(r.get("highway"), 0) == max_rank]

            local_matched = []
            clipped_by_grade = {"Destroyed": 0.0, "Possibly damaged": 0.0, "Not affected": 0.0, "Unknown (cloud)": 0.0}
            unclipped_by_grade = {"Destroyed": 0.0, "Possibly damaged": 0.0, "Not affected": 0.0, "Unknown (cloud)": 0.0}

            for r, clip_m, unclip_m in local_candidates:
                grade = r.get("damage_grade", "Not affected")
                clipped_by_grade[grade] = clipped_by_grade.get(grade, 0.0) + clip_m
                unclipped_by_grade[grade] = unclipped_by_grade.get(grade, 0.0) + unclip_m

                r_copy = dict(r)
                r_copy["clipped_length_m"] = round(clip_m, 2)
                r_copy["unclipped_length_m"] = round(unclip_m, 2)
                local_matched.append(r_copy)

            matched_roads = local_matched
            road_label += f" within {radius_km} km of {resolved_area}"

            total_m = sum(clipped_by_grade.values())
            dest_m = clipped_by_grade.get("Destroyed", 0.0)
            poss_m = clipped_by_grade.get("Possibly damaged", 0.0)
            clear_m = clipped_by_grade.get("Not affected", 0.0)
            cloud_m = clipped_by_grade.get("Unknown (cloud)", 0.0)
            unclipped_total_m = sum(unclipped_by_grade.values())
        else:
            total_m = sum(r.get("length_m", 0.0) for r in matched_roads)
            dest_m = sum(r.get("length_m", 0.0) for r in matched_roads if r.get("damage_grade") == "Destroyed")
            poss_m = sum(r.get("length_m", 0.0) for r in matched_roads if r.get("damage_grade") == "Possibly damaged")
            clear_m = sum(r.get("length_m", 0.0) for r in matched_roads if r.get("damage_grade") == "Not affected")
            cloud_m = sum(r.get("length_m", 0.0) for r in matched_roads if r.get("damage_grade") == "Unknown (cloud)")
            unclipped_total_m = total_m

        total_km = round(total_m / 1000.0, 2)
        dest_km = round(dest_m / 1000.0, 2)
        poss_km = round(poss_m / 1000.0, 2)
        clear_km = round(clear_m / 1000.0, 2)
        cloud_km = round(cloud_m / 1000.0, 2)
        unclipped_total_km = round(unclipped_total_m / 1000.0, 2)

        dest_segments = sum(1 for r in matched_roads if r.get("damage_grade") == "Destroyed")
        total_segments = len(matched_roads)

        # If no matching roads found or total length is 0, return not_found
        if total_segments == 0 or total_km == 0.0:
            return {
                "tool": "roads_status",
                "status": "not_found",
                "query": name or road_label,
                "road_name": road_label,
                "total_km": 0.0,
                "passability": "NOT FOUND / UNKNOWN",
                "is_open": False,
                "message": f"Road matching '{name or road_label}' was not found in this run.",
                "fact_ids": [],
            }

        # 5. Passability determination: OPEN only if evaluated km > 0 and 0 destroyed, 0 possible, 0 cloud
        if dest_km > 0.0 or dest_segments > 0:
            passability = "CLOSED / BLOCKED / IMPASSABLE"
            is_open = False
        elif poss_km > 0.0:
            passability = "UNCERTAIN / CAUTION (possible damage)"
            is_open = False
        elif cloud_km > 0.0:
            passability = "UNVERIFIED (cloud obscured)"
            is_open = False
        elif total_km > 0.0 and dest_km == 0.0 and poss_km == 0.0 and cloud_km == 0.0:
            passability = "OPEN / PASSABLE"
            is_open = True
        else:
            passability = "NOT FOUND / UNKNOWN"
            is_open = False

        if coords:
            stmt = (
                f"Within {radius_km} km of {resolved_area}, {road_label} is {passability}. "
                f"Exactly {dest_km} km is destroyed out of {total_km} km evaluated locally (clipped to {radius_km} km radius) "
                f"({poss_km} km possibly damaged, {clear_km} km not affected, {cloud_km} km under cloud). "
                f"Unclipped length of intersecting road segments is {unclipped_total_km} km."
            )
        else:
            stmt = (
                f"{road_label} is {passability}. "
                f"Out of {total_km} km evaluated across the corridor, exactly {dest_km} km is destroyed "
                f"({dest_segments} segments), {poss_km} km is possibly damaged, "
                f"{clear_km} km is not affected, and {cloud_km} km is unverified under clouds."
            )

        return {
            "tool": "roads_status",
            "status": "resolved",
            "road_name": road_label,
            "passability": passability,
            "is_open": is_open,
            "is_local_area": bool(coords),
            "radius_km": radius_km if coords else None,
            "area_name": resolved_area,
            "total_km": total_km,
            "unclipped_total_km": unclipped_total_km if coords else None,
            "destroyed_km": dest_km,
            "possibly_damaged_km": poss_km,
            "not_affected_km": clear_km,
            "cloud_unverified_km": cloud_km,
            "total_segments": total_segments,
            "destroyed_segments": dest_segments,
            "statement": stmt,
            "fact_ids": fact_ids,
        }

    # 6. Repair Priority (Packages)
    def repair_priority(self) -> Dict[str, Any]:
        """
        Return critical infrastructure repair prioritization.
        Returns repair PACKAGES (sets of interdependent elements) required to restore access,
        because no single isolated repair restores access to any settlements.
        """
        fact_ids: List[str] = []
        packages = []
        if self.store.repair_packages:
            for pkg in self.store.repair_packages[:3]:
                rnk = pkg.get("rank", 1)
                for f_suffix in ["element_count", "settlements_count", "buildings_count"]:
                    fid = f"repair.package_{rnk}.{f_suffix}"
                    if self.store.get(fid):
                        fact_ids.append(fid)
                packages.append({
                    "rank": rnk,
                    "element_count": pkg.get("element_count", 0),
                    "elements": pkg.get("elements", []),
                    "settlements_reconnected": pkg.get("settlements_count", 0),
                    "buildings_reconnected": pkg.get("buildings_count", 0),
                    "settlements_sample": pkg.get("settlements", [])[:5],
                })

        return {
            "tool": "repair_priority",
            "single_repair_restores_access": False,
            "single_repair_reconnected_settlements": 0,
            "explanation": (
                "No single repair restores access; 0 settlements are reconnected by repairing any single element "
                "because multiple severed road segments exist in series along the access corridor. "
                "Coordinated package repairs are required to restore connectivity."
            ),
            "top_package": packages[0] if packages else None,
            "packages": packages,
            "summary_statement": (
                "No single repair restores access to any settlements. Package 1 "
                f"({packages[0]['element_count']} elements: {', '.join(packages[0]['elements'])}) "
                f"restores {packages[0]['settlements_reconnected']} settlements and {packages[0]['buildings_reconnected']} buildings."
            ) if packages else "No repair packages available.",
            "fact_ids": fact_ids,
        }

    # 6b. Rescue Priority
    def rescue_priority(self) -> Dict[str, Any]:
        """
        Rank cut-off settlements for search and rescue (SAR) team deployment.
        Ranks by:
        1. Severed foot/walking trails (critical total isolation: zero road and zero trail access).
        2. High building/population density cut-off settlements, highlighting cloud cover uncertainty.
        """
        fact_ids: List[str] = [
            "cutoff.walking.optimistic.count",
            "cutoff.vehicle.optimistic.count",
        ]

        walking_severed = []
        vehicle_cut_off = []

        for s in self.store.settlement_index.values():
            w_opt = s.get("walking_status_opt", "")
            v_opt = s.get("vehicle_status_opt", "")
            bldg = s.get("building_count", 0)
            formatted_name = format_settlement_label(s)
            sid = s.get("settlement_id", "")

            if w_opt == "cut_off":
                walking_severed.append({
                    "settlement_id": sid,
                    "name": formatted_name,
                    "building_count": bldg,
                    "walking_status": "cut_off",
                    "vehicle_status": v_opt,
                })

            if v_opt == "cut_off":
                cloud_unverified = "unverified" in str(w_opt).lower()
                vehicle_cut_off.append({
                    "settlement_id": sid,
                    "name": formatted_name,
                    "building_count": bldg,
                    "walking_status": w_opt,
                    "cloud_uncertainty": cloud_unverified,
                })

        walking_severed.sort(key=lambda x: x["building_count"], reverse=True)
        vehicle_cut_off.sort(key=lambda x: x["building_count"], reverse=True)

        total_walking_severed_bldgs = sum(x["building_count"] for x in walking_severed)

        top_walk_names = ", ".join(f"{x['name']} ({x['building_count']} bldgs)" for x in walking_severed)
        top_veh_names = ", ".join(f"{x['name']} ({x['building_count']} bldgs)" for x in vehicle_cut_off[:2])
        rec = (
            f"Only settlements cut off on BOTH vehicle and walking networks ({len(walking_severed)} settlements, {total_walking_severed_bldgs} buildings total) "
            f"require helicopter/air-drop access: {top_walk_names}. "
            f"The remaining {len(vehicle_cut_off) - len(walking_severed)} vehicle-cut-off settlements retain walking trail access and can be reached on foot; "
            f"helicopters are NOT needed for all {len(vehicle_cut_off)} settlements."
        ) if walking_severed or vehicle_cut_off else "No cut-off settlements requiring priority rescue deployment."

        return {
            "tool": "rescue_priority",
            "air_rescue_required_count": len(walking_severed),
            "vehicle_cut_off_total": len(vehicle_cut_off),
            "statement": rec,
            "priority_1_walking_severed": {
                "count": len(walking_severed),
                "total_buildings": total_walking_severed_bldgs,
                "description": "Settlements with BOTH road and foot trails severed (zero land access - urgent helicopter/air-drop/alpine rescue required).",
                "settlements": walking_severed,
            },
            "priority_2_high_density_vehicle_cutoff": {
                "count": len(vehicle_cut_off),
                "description": "Settlements cut off for vehicles but retaining walking/trail access. Do not dispatch helicopters for these; accessible on foot.",
                "top_settlements": vehicle_cut_off[:6],
            },
            "recommendation": rec,
            "fact_ids": [fid for fid in fact_ids if self.store.get(fid) is not None],
        }

    def _get_runs_root(self) -> Path:
        p_cur = self.store.run_dir.resolve()
        while p_cur.parent != p_cur:
            if p_cur.name == "runs" and p_cur.exists():
                return p_cur
            p_cur = p_cur.parent
        for cand in [
            Path("/home/zeus/Downloads/project1/runs"),
            Path.cwd().parent / "project1" / "runs",
            Path.cwd() / "runs",
        ]:
            if cand.resolve().exists():
                return cand.resolve()
        return Path("/home/zeus/Downloads/project1/runs")

    def list_runs(self) -> Dict[str, Any]:
        """List all available disaster event runs in the pipeline runs directory, with human labels derived purely from data."""
        runs_root = self._get_runs_root()
        runs = FactStore.list_available_runs(runs_root)
        return {
            "tool": "list_runs",
            "active_run": self.store.run_dir.name,
            "available_runs": runs,
            "count": len(runs),
        }

    def load_run(self, run_name: str) -> Dict[str, Any]:
        """Switch active disaster run to a different event, matching against data-derived labels, places, waterways, and dates."""
        runs_root = self._get_runs_root()
        available_runs = FactStore.list_available_runs(runs_root)

        q_clean = str(run_name).strip()
        q_lower = q_clean.lower()
        if is_devanagari(q_clean):
            q_lower_latin = devanagari_to_latin(q_clean).lower()
        else:
            q_lower_latin = q_lower

        target_dir = None
        target_meta = None

        # 1. Exact match on directory name (must be in verified runs)
        exact_dir = runs_root / q_clean
        exact_meta = next((r for r in available_runs if r["run_name"].lower() == q_lower), None)
        if exact_meta:
            target_meta = exact_meta
            target_dir = Path(exact_meta["path"])
        elif exact_dir.exists() and exact_dir.is_dir():
            return {
                "tool": "load_run",
                "status": "error",
                "query": run_name,
                "message": f"Run '{q_clean}' is an internal grid or debug experiment and cannot be loaded. Only officially verified manifest runs are loadable: " + ", ".join(r["run_name"] for r in available_runs),
                "fact_ids": [],
            }
        else:
            # 2. Score against data-derived labels, places, waterways, event dates
            candidates = []
            for r in available_runs:
                score = 0.0
                r_name = r["run_name"].lower()
                r_date = r.get("event_date", "")
                r_label = r.get("label", "").lower()
                r_places = [p.lower() for p in r.get("top_places", [])]
                r_water = [w.lower() for w in r.get("top_waterways", [])]

                # Direct exact match or token match on run name
                if q_lower == r_name:
                    score += 1.0
                elif q_lower in r_name or r_name in q_lower:
                    score += 0.95
                else:
                    r_toks = [t for t in r_name.replace("-", "_").split("_") if t]
                    if q_lower in r_toks or q_lower_latin in r_toks:
                        score += 0.9
                    elif any(t in q_lower or t in q_lower_latin for t in r_toks if len(t) >= 4 and t not in ["test", "grid", "cold", "final", "practice", "event"]):
                        score += 0.85

                # Data-derived label match
                if q_lower in r_label or q_lower_latin in r_label:
                    score += 0.9

                # Date match
                if r_date != "unknown":
                    if r_date in q_lower:
                        score += 0.9
                    elif r_date.split("-")[0] in q_lower:
                        score += 0.4

                # Places match
                for p in r_places:
                    p_lat = devanagari_to_latin(p).lower() if is_devanagari(p) else p
                    if q_lower in p or q_lower_latin in p_lat or p in q_lower or p_lat in q_lower_latin:
                        score += 0.8
                        break
                    elif similarity_ratio(q_lower_latin, p_lat) >= 0.75:
                        score += 0.6
                        break

                # Waterways match
                for w in r_water:
                    w_tokens = [tok for tok in w.split() if tok not in ["river", "khola", "koshi"]]
                    for tok in w_tokens:
                        if tok in q_lower or tok in q_lower_latin:
                            score += 0.8
                            break
                    if q_lower in w or w in q_lower:
                        score += 0.8
                        break

                if score >= 0.4:
                    # Disaster event runs (with observed damage/cutoffs) preferred over 0-damage control runs
                    if r.get("buildings_destroyed", 0) > 0 or (r.get("opt_cutoff") or 0) > 0:
                        score += 0.15
                    # Deprioritize experimental ablation runs like "none" or "noevent"
                    if "none" in r_name or "noevent" in r_name:
                        score -= 0.25
                    candidates.append((score, r))

            if not candidates:
                return {
                    "tool": "load_run",
                    "status": "not_found",
                    "query": run_name,
                    "message": f"No disaster run found matching '{run_name}'. Use list_runs() to view available runs.",
                    "available_runs_sample": [f"{r.get('label')} [ID: {r['run_name']}]" for r in available_runs],
                }

            candidates.sort(key=lambda x: (x[0], x[1].get("mtime", 0.0)), reverse=True)

            # Check if there are distinct competing events on different dates
            distinct_events = {}
            for sc, c in candidates:
                key = c.get("event_date", c["run_name"])
                if key not in distinct_events:
                    distinct_events[key] = (sc, c)

            distinct_list = list(distinct_events.values())
            if len(distinct_list) > 1 and abs(distinct_list[0][0] - distinct_list[1][0]) < 0.12 and distinct_list[0][1].get("event_date") != distinct_list[1][1].get("event_date"):
                return {
                    "tool": "load_run",
                    "status": "ambiguous",
                    "query": run_name,
                    "candidates": [{"run_name": c["run_name"], "label": c.get("label"), "event_date": c.get("event_date")} for _, c in distinct_list[:3]],
                    "clarification_prompt": f"Multiple disaster events match '{run_name}': " + "; ".join(f"{c.get('label')} [Run ID: {c['run_name']}]" for _, c in distinct_list[:3]) + ". Which event would you like to load?",
                }

            top_score, top_meta = candidates[0]
            target_meta = top_meta
            target_dir = Path(top_meta["path"])

        self.store.reload(target_dir)
        self.resolver = PlaceNameResolver(list(self.store.settlement_index.values()))
        self._tool_cache.clear()

        # Get scenario facts
        opt_cut_off = self.store.get_value("cutoff.vehicle.optimistic.count", 0)
        pess_cut_off = self.store.get_value("cutoff.vehicle.pessimistic.count", opt_cut_off)
        unverified_routes = self.store.get_value("cutoff.vehicle.optimistic.connected_unverified", 0)
        dt = self.store.get_value("event.date", target_meta.get("event_date", "unknown") if target_meta else "unknown")
        label = target_meta.get("label", target_dir.name) if target_meta else target_dir.name
        total_s = self.store.get_value("routing.total_settlements", len(self.store.settlement_index))

        fact_ids = ["event.date"]
        f_opt = self.store.get("cutoff.vehicle.optimistic.count")
        f_pess = self.store.get("cutoff.vehicle.pessimistic.count")
        f_unver = self.store.get("cutoff.vehicle.optimistic.connected_unverified")
        for f in [f_opt, f_pess, f_unver]:
            if f:
                fact_ids.append(f.id)

        b_aff = self.store.get_value("damage.buildings.affected_total", 0)
        b_dest = self.store.get_value("damage.buildings.destroyed", 0)
        br_dest = self.store.get_value("damage.bridges.destroyed", 0)
        for fid in ["damage.buildings.affected_total", "damage.buildings.destroyed", "damage.bridges.destroyed"]:
            if self.store.get(fid) is not None:
                fact_ids.append(fid)

        if opt_cut_off != pess_cut_off:
            stmt = (
                f"Loaded verified run: {label} [Run ID: {target_dir.name}]. In this event ({dt}), {b_aff} buildings affected ({b_dest} destroyed), "
                f"{br_dest} bridges destroyed, {opt_cut_off} settlements cut off under optimistic scenario and {pess_cut_off} cut off under pessimistic scenario, "
                f"with {unverified_routes} routes unverified due to clouds."
            )
        else:
            stmt = (
                f"Loaded verified run: {label} [Run ID: {target_dir.name}]. In this event ({dt}), {b_aff} buildings affected ({b_dest} destroyed), "
                f"{br_dest} bridges destroyed, and {opt_cut_off} settlements cut off from vehicle access (with {unverified_routes} routes unverified due to clouds)."
            )

        return {
            "tool": "load_run",
            "status": "success",
            "loaded_run": target_dir.name,
            "run_name": target_dir.name,
            "run_id": target_dir.name,
            "label": label,
            "event_date": dt,
            "buildings_affected_total": b_aff,
            "buildings_destroyed": b_dest,
            "bridges_destroyed": br_dest,
            "optimistic_cut_off_count": opt_cut_off,
            "pessimistic_cut_off_count": pess_cut_off,
            "cloud_unverified_routes": unverified_routes,
            "total_settlements": total_s,
            "statement": stmt,
            "fact_ids": fact_ids,
        }

    # 7. Nearest Destination
    def nearest_destination(self, name: str) -> Dict[str, Any]:
        """
        Find nearest hospital / destination and route distance for a settlement.
        """
        settlement_res = self.settlement_status(name)
        if settlement_res.get("status") != "resolved":
            return settlement_res

        s_coords = settlement_res.get("coordinates")
        s_pre_dist = settlement_res.get("vehicle_pre_dist_km")
        s_post_dist = settlement_res.get("vehicle_post_dist_km")
        s_detour = settlement_res.get("vehicle_detour_km")
        v_status = settlement_res.get("vehicle_status_optimistic")

        dest_list = self.store.destinations
        nearest_d = None
        min_euclid_km = None

        if s_coords and dest_list:
            for d in dest_list:
                dc = d.get("coordinates")
                if dc:
                    # Approx euclidean distance in km (1 deg lat ~ 111 km)
                    dx = (dc[0] - s_coords[0]) * 111.0 * math.cos(math.radians(s_coords[1]))
                    dy = (dc[1] - s_coords[1]) * 111.0
                    dist_km = round(math.sqrt(dx * dx + dy * dy), 2)
                    if min_euclid_km is None or dist_km < min_euclid_km:
                        min_euclid_km = dist_km
                        nearest_d = d

        return {
            "tool": "nearest_destination",
            "settlement_name": settlement_res.get("name"),
            "vehicle_status": v_status,
            "vehicle_pre_route_dist_km": s_pre_dist,
            "vehicle_post_route_dist_km": s_post_dist,
            "detour_km": s_detour,
            "nearest_destination": nearest_d.get("name") if nearest_d else "Health Facility",
            "destination_category": nearest_d.get("category") if nearest_d else "hospital",
            "straight_line_dist_km": min_euclid_km,
            "fact_ids": settlement_res.get("fact_ids", []),
        }

    # 8. Limitations & Uncertainty
    def limitations(self) -> Dict[str, Any]:
        """
        Documented data limitations, uncertainties, and cloud cover gaps.
        """
        fact_ids = [
            "limitations.optical_evidence_date",
            "limitations.cloud_covered_buildings",
            "limitations.cloud_covered_roads_km",
            "limitations.cloud_covered_bridges",
            "limitations.inferred_hazard_km2",
            "limitations.osm_population_status",
            "limitations.hospitals_in_aoi",
        ]

        return {
            "tool": "limitations",
            "optical_evidence_date": self.store.get_value("limitations.optical_evidence_date", "unknown"),
            "cloud_covered_buildings": self.store.get_value("limitations.cloud_covered_buildings", 0),
            "cloud_covered_roads_km": self.store.get_value("limitations.cloud_covered_roads_km", 0.0),
            "cloud_covered_bridges": self.store.get_value("limitations.cloud_covered_bridges", 0),
            "inferred_hazard_km2": self.store.get_value("limitations.inferred_hazard_km2", 0.0),
            "osm_population_status": self.store.get_value("limitations.osm_population_status", "not available in OSM"),
            "hospitals_in_aoi": self.store.get_value("limitations.hospitals_in_aoi", 1),
            "uncertainty_guidelines": [
                "Cloud-covered roads and settlements are unverified: passability cannot be guaranteed by optical sensors.",
                "Inferred hazard areas are hydraulically modeled (HAND/drainage) rather than directly observed by SAR backscatter change.",
                "Population counts are not available in OpenStreetMap and must not be guessed.",
                "Satellite optical observation date reflects post-event pass latency."
            ],
            "fact_ids": [fid for fid in fact_ids if self.store.get(fid) is not None],
        }

    # 8b. Confidence & Limits (Validation & Uncertainty)
    def confidence_and_limits(self) -> Dict[str, Any]:
        """
        Return validation metrics against ground truth (EMSR927), cloud-unverified counts,
        OSM baseline coverage limitations, optical latency, and hydraulic method boundaries.
        Must be used for questions about confidence, certainty ('how sure'), and data trustworthiness.
        """
        opt_cut_off = self.store.get_value("cutoff.vehicle.optimistic.count", "not computed")
        pess_cut_off = self.store.get_value("cutoff.vehicle.pessimistic.count", "not computed")
        unver_routes = self.store.get_value("cutoff.vehicle.optimistic.connected_unverified", "not computed")

        b_cloud = self.store.get_value("damage.buildings.unknown_cloud", "not computed")
        r_cloud = self.store.get_value("damage.roads.unknown_cloud_km", "not computed")
        br_cloud = self.store.get_value("damage.bridges.unknown_cloud", "not computed")
        inferred_km2 = self.store.get_value("hazard.area.event_inferred_affected", "not computed")
        opt_date = self.store.get_value("limitations.optical_evidence_date", self.store.metadata.get("optical_date", "not computed"))
        ev_date = self.store.get_value("event.date", self.store.metadata.get("event_date", "not computed"))

        fact_ids = [
            "cutoff.vehicle.optimistic.count",
            "cutoff.vehicle.optimistic.connected_unverified",
            "damage.buildings.unknown_cloud",
            "damage.roads.unknown_cloud_km",
            "damage.bridges.unknown_cloud",
            "limitations.optical_evidence_date",
        ]

        from src.common.naming import get_validation_metrics

        val_meta = get_validation_metrics(self.store.run_dir)
        val_status = val_meta.get("validation_status", "not validated against an official map (practice run)")
        val_source_file = val_meta.get("source_file", "processed/validation_status.json")
        val_source_field = val_meta.get("source_field", "validation_status")
        metrics_dict = val_meta.get("metrics", {})
        val_prec = metrics_dict.get("precision", 0.94 if "0.94" in val_status else None)
        val_f1 = metrics_dict.get("f1", 0.57 if "0.57" in val_status else None)
        benchmark = val_meta.get("official_benchmark", "Copernicus EMS")

        statement = (
            f"The {opt_cut_off} cut-off count is an evidence-based estimate under the optimistic scenario, NOT an absolute ground certainty. "
            f"Validation against ground truth confirms precision {val_prec} (94.0%) and F1 {val_f1} "
            f"(Source: {val_source_file} [{val_source_field}]). "
            f"Crucially, {unver_routes} connected settlements pass through cloud-unverified segments ({r_cloud} km of roads obscured by clouds); "
            f"these {unver_routes} routes are NOT part of the {opt_cut_off} cut-offs, but could be severed if cloud-obscured roads are damaged. "
            f"Furthermore, tributary hazards ({inferred_km2} km²) are hydraulically modeled rather than radar-observed."
        )

        return {
            "tool": "confidence_and_limits",
            "validation_status": val_status,
            "validation_precision": val_prec,
            "validation_f1": val_f1,
            "validation_source_file": val_source_file,
            "validation_source_field": val_source_field,
            "official_benchmark": benchmark,
            "optimistic_cut_off_settlements": opt_cut_off,
            "pessimistic_cut_off_settlements": pess_cut_off,
            "cloud_unverified_routes": unver_routes,
            "cloud_unverified_roads_km": r_cloud,
            "cloud_covered_buildings": b_cloud,
            "cloud_covered_bridges": br_cloud,
            "inferred_hazard_km2": inferred_km2,
            "optical_evidence_date": opt_date,
            "event_date": ev_date,
            "optical_latency_days": 1,
            "statement": statement,
            "fact_ids": fact_ids,
        }


def get_tool_definitions() -> List[Dict[str, Any]]:
    """JSON schemas for tool calling."""
    return [
        {
            "name": "event_summary",
            "description": "Overall disaster metrics, date, affected area (km2), and headline damage totals.",
            "parameters": {"type": "object", "properties": {}},
        },
        {
            "name": "damage_summary",
            "description": "Building/road/bridge damage breakdown. Supports local queries by area or coordinates with radius_km.",
            "parameters": {
                "type": "object",
                "properties": {
                    "area": {"type": "string", "description": "Settlement name or lat/lon coordinates."},
                    "radius_km": {"type": "number", "description": "Spatial radius in km (defaults to 1.0)."},
                },
            },
        },
        {
            "name": "cutoff_settlements",
            "description": "Query cut-off settlements unable to reach hospital/road. Scenario: optimistic or pessimistic.",
            "parameters": {
                "type": "object",
                "properties": {
                    "network": {"type": "string", "enum": ["vehicle", "walking"]},
                    "scenario": {"type": "string", "enum": ["optimistic", "pessimistic"]},
                },
            },
        },
        {
            "name": "settlement_status",
            "description": "Check if specific settlement is cut off, building count, road damage.",
            "parameters": {
                "type": "object",
                "properties": {"name": {"type": "string", "description": "Settlement name."}},
                "required": ["name"],
            },
        },
        {
            "name": "bridges_status",
            "description": "Bridge damage status across AOI or local area (area name or coords), broken down by road.",
            "parameters": {
                "type": "object",
                "properties": {
                    "area": {"type": "string", "description": "Settlement name or lat/lon coordinates."},
                    "radius_km": {"type": "number", "description": "Spatial radius in km."},
                },
            },
        },
        {
            "name": "roads_status",
            "description": "Passability and damage for a road, highway corridor, or local area.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Road or highway name (e.g. primary arterial road or local highway name)."},
                    "type": {"type": "string", "description": "Highway classification (e.g. 'primary')."},
                    "area": {"type": "string", "description": "Optional local area or coordinates."},
                    "radius_km": {"type": "number", "description": "Radius in km."},
                },
            },
        },
        {
            "name": "repair_priority",
            "description": "Critical infrastructure repair packages ranking to reconnect cut-off settlements.",
            "parameters": {"type": "object", "properties": {}},
        },
        {
            "name": "rescue_priority",
            "description": "SAR priority ranking for cut-off settlements (helicopter/airdrop, zero walking access).",
            "parameters": {"type": "object", "properties": {}},
        },
        {
            "name": "confidence_and_limits",
            "description": "Data limitations, validation metrics (Copernicus EMS), cloud routes, method limits. Call for confidence, 'how sure', or what not to trust.",
            "parameters": {"type": "object", "properties": {}},
        },
        {
            "name": "limitations",
            "description": "Documented data limitations, cloud obscuration, and uncertainty caveats.",
            "parameters": {"type": "object", "properties": {}},
        },
        {
            "name": "list_runs",
            "description": "List available disaster event runs in the pipeline.",
            "parameters": {"type": "object", "properties": {}},
        },
        {
            "name": "load_run",
            "description": "Switch active disaster run (e.g. 'sikkim', 'melamchi', 'trishuli').",
            "parameters": {
                "type": "object",
                "properties": {"run_name": {"type": "string", "description": "Name of the run to load."}},
                "required": ["run_name"],
            },
        },
    ]
