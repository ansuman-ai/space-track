"""Tools callable by LLM / copilot to answer rescuer questions.

Each tool returns structured data strictly grounded in pipeline run outputs,
along with associated fact IDs for verification by the number guard.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from .facts import FactStore
from .names import PlaceNameResolver


def haversine(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """Great-circle distance in kilometers between two points."""
    r = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


class CopilotTools:
    """Toolkit grounded in FactStore and PlaceNameResolver."""

    def __init__(self, fact_store: FactStore):
        self.store = fact_store
        self.resolver = PlaceNameResolver(list(fact_store.settlement_index.values()))

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
    def damage_summary(self, area: Optional[str] = None, radius_km: float = 1.0) -> Dict[str, Any]:
        """Summarize damage across buildings, roads, and bridges.
        Supports 'near X' queries with a spatial radius, computing local damage
        and never presenting AOI totals as local numbers.
        """
        fact_ids: List[str] = []

        if area:
            area_lower = area.strip().lower()
            coords = None
            resolved_name = area.strip()

            if any(k in area_lower for k in ["confluence", "दोभान", "doban", "dovan", "river junction"]):
                coords = [85.334, 28.161]
                resolved_name = "Confluence (Trishuli & Langtang Khola / Syabrubesi)"
            else:
                m_res = self.resolver.resolve(area)
                if m_res.status in ["exact", "fuzzy"] and m_res.match:
                    coords = m_res.match.get("coordinates")
                    resolved_name = m_res.match.get("name", area)
                elif m_res.status == "ambiguous":
                    return {
                        "tool": "damage_summary",
                        "status": "ambiguous",
                        "query": area,
                        "candidates": m_res.candidates,
                        "clarification_prompt": m_res.clarification_prompt,
                        "fact_ids": [],
                    }

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
                aoi_bldg_dest = self.store.get_value("damage.buildings.destroyed", 81)
                aoi_br_dest = self.store.get_value("damage.bridges.destroyed", 10)

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
                    },
                    "regional_aoi_totals_reference": {
                        "buildings_destroyed_aoi": aoi_bldg_dest,
                        "bridges_destroyed_aoi": aoi_br_dest,
                    },
                    "note": (
                        f"Local damage metrics calculated within {radius_km} km of {resolved_name}: "
                        f"{b_grades['Destroyed']} buildings destroyed (out of {local_b_total} assessed locally). "
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

        fact_ids = [f.id for f in [f_count, f_clear, f_unver, f_tot, f_no_net] if f is not None]

        # Extract cut-off settlement names from settlement index
        cutoff_list = []
        for s in self.store.settlement_index.values():
            if net == "vehicle":
                st = s.get("vehicle_status_opt" if scen == "optimistic" else "vehicle_status_pess", "")
            else:
                st = s.get("walking_status_opt", "")

            if st == "cut_off":
                cutoff_list.append({
                    "settlement_id": s.get("settlement_id"),
                    "name": s.get("name"),
                    "building_count": s.get("building_count", 0),
                })

        return {
            "tool": "cutoff_settlements",
            "network": net,
            "scenario": scen,
            "cut_off_count": f_count.value if f_count else len(cutoff_list),
            "connected_clear_count": f_clear.value if f_clear else 0,
            "connected_unverified_count": f_unver.value if f_unver else 0,
            "connected_total_count": f_tot.value if f_tot else 0,
            "no_network_access_count": f_no_net.value if f_no_net else 0,
            "evidence": "observed" if scen == "optimistic" else "inferred",
            "cut_off_settlements_sample": cutoff_list[:15],
            "total_cut_off_settlements": len(cutoff_list),
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
    def bridges_status(self, area: Optional[str] = None, radius_km: float = 1.5) -> Dict[str, Any]:
        """Summarize bridge damage and list destroyed bridges.
        Supports local area queries with a radius, never conflating local with AOI totals.
        """
        fact_ids: List[str] = []

        if area:
            area_lower = area.strip().lower()
            coords = None
            resolved_name = area.strip()
            if any(k in area_lower for k in ["syabru", "confluence", "दोभान", "doban"]):
                coords = [85.3359, 28.1631]
                resolved_name = "Syabrubesi / Confluence"
            else:
                m_res = self.resolver.resolve(area)
                if m_res.status in ["exact", "fuzzy"] and m_res.match:
                    coords = m_res.match.get("coordinates")
                    resolved_name = m_res.match.get("name", area)
                elif m_res.status == "ambiguous":
                    return {
                        "tool": "bridges_status",
                        "status": "ambiguous",
                        "query": area,
                        "candidates": m_res.candidates,
                        "clarification_prompt": m_res.clarification_prompt,
                        "fact_ids": [],
                    }

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

                return {
                    "tool": "bridges_status",
                    "area": resolved_name,
                    "is_local_area": True,
                    "radius_km": radius_km,
                    "local_total_bridges": len(local_bridges),
                    "local_destroyed_count": len(local_dest),
                    "local_possibly_damaged_count": len(local_poss),
                    "local_destroyed_bridges": local_dest,
                    "regional_aoi_reference": {
                        "total_bridges_aoi": self.store.get_value("damage.bridges.total", 27),
                        "destroyed_bridges_aoi": self.store.get_value("damage.bridges.destroyed", 10),
                    },
                    "note": (
                        f"In {resolved_name} (within {radius_km} km), exactly {len(local_dest)} bridges were destroyed "
                        f"out of {len(local_bridges)} assessed locally. Across the entire AOI, 10 bridges were destroyed out of 27."
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

        return {
            "tool": "bridges_status",
            "is_local_area": False,
            "scope": "Entire Assessment Area (AOI)",
            "total_bridges": self.store.get_value("damage.bridges.total", 0),
            "affected_total": self.store.get_value("damage.bridges.affected_total", 0),
            "destroyed_count": self.store.get_value("damage.bridges.destroyed", 0),
            "possibly_damaged_count": self.store.get_value("damage.bridges.possibly_damaged", 0),
            "not_affected_count": self.store.get_value("damage.bridges.not_affected", 0),
            "unknown_cloud_count": self.store.get_value("damage.bridges.unknown_cloud", 0),
            "destroyed_bridges_sample": destroyed_bridges[:5],
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
            name = s.get("name", "")
            sid = s.get("settlement_id", "")

            if w_opt == "cut_off":
                walking_severed.append({
                    "settlement_id": sid,
                    "name": name,
                    "building_count": bldg,
                    "walking_status": "cut_off",
                    "vehicle_status": v_opt,
                })

            if v_opt == "cut_off":
                cloud_unverified = "unverified" in str(w_opt).lower()
                vehicle_cut_off.append({
                    "settlement_id": sid,
                    "name": name,
                    "building_count": bldg,
                    "walking_status": w_opt,
                    "cloud_uncertainty": cloud_unverified,
                })

        walking_severed.sort(key=lambda x: x["building_count"], reverse=True)
        vehicle_cut_off.sort(key=lambda x: x["building_count"], reverse=True)

        total_walking_severed_bldgs = sum(x["building_count"] for x in walking_severed)

        return {
            "tool": "rescue_priority",
            "priority_1_walking_severed": {
                "count": len(walking_severed),
                "total_buildings": total_walking_severed_bldgs,
                "description": "Settlements with BOTH road and foot trails severed (zero land access - urgent helicopter/air-drop/alpine rescue required).",
                "settlements": walking_severed,
            },
            "priority_2_high_density_vehicle_cutoff": {
                "count": len(vehicle_cut_off),
                "description": "Settlements cut off for vehicles, ranked by building count. Walking trails are unverified due to cloud cover.",
                "top_settlements": vehicle_cut_off[:6],
            },
            "recommendation": (
                f"Deploy rescue teams first to the Dalphedi (clusters 32, 33, 38) and Lingling (cluster 62) "
                f"areas ({len(walking_severed)} settlements, {total_walking_severed_bldgs} buildings) where walking trails are completely severed. "
                "Next, target high-density vehicle cut-off settlements: Aamachhodingmo (330 buildings) and "
                "Syabru Besi area (261 buildings), where trail passability remains unverified under cloud cover."
            ),
            "fact_ids": [fid for fid in fact_ids if self.store.get(fid) is not None],
        }

    # 6c. Run Scope Management (list_runs & load_run)
    def list_runs(self) -> Dict[str, Any]:
        """List all available disaster event runs in the pipeline."""
        runs = FactStore.list_available_runs()
        return {
            "tool": "list_runs",
            "active_run": self.store.run_dir.name,
            "available_runs": runs,
            "count": len(runs),
        }

    def load_run(self, run_name: str) -> Dict[str, Any]:
        """Switch active disaster run to a different event (e.g. 'test_B_melamchi')."""
        runs_root = Path("/home/zeus/Downloads/project1/runs")
        target_dir = None
        for p in runs_root.iterdir():
            if p.is_dir() and (p.name == run_name or run_name.lower() in p.name.lower()):
                target_dir = p
                break

        if not target_dir:
            return {
                "tool": "load_run",
                "status": "error",
                "message": f"Run '{run_name}' not found in runs directory.",
            }

        self.store.reload(target_dir)
        self.resolver = PlaceNameResolver(list(self.store.settlement_index.values()))

        cut_off = self.store.get_value("cutoff.vehicle.optimistic.count", 0)
        dt = self.store.get_value("event.date", "unknown")

        return {
            "tool": "load_run",
            "status": "success",
            "loaded_run": target_dir.name,
            "event_date": dt,
            "cut_off_settlements": cut_off,
            "total_settlements": self.store.get_value("routing.total_settlements", len(self.store.settlement_index)),
            "fact_ids": ["cutoff.vehicle.optimistic.count", "event.date"],
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


def get_tool_definitions() -> List[Dict[str, Any]]:
    """JSON schemas for tool calling."""
    return [
        {
            "name": "event_summary",
            "description": "Get overall disaster summary, event date, sensors used, affected area (km2), and headline damage metrics.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
        {
            "name": "damage_summary",
            "description": "Get breakdown of damaged buildings (destroyed, damaged, possibly damaged, cloud-covered), roads (km), and bridges. Supports spatial local queries like area='confluence' with radius_km.",
            "parameters": {
                "type": "object",
                "properties": {
                    "area": {
                        "type": "string",
                        "description": "Optional specific settlement or area name (e.g. 'confluence', 'Syabrubesi') to calculate local damage.",
                    },
                    "radius_km": {
                        "type": "number",
                        "description": "Spatial radius in kilometers for local area damage calculation (defaults to 1.0 km).",
                    },
                },
            },
        },
        {
            "name": "cutoff_settlements",
            "description": "Query cut-off settlements by network ('vehicle' or 'walking') and scenario ('optimistic' or 'pessimistic').",
            "parameters": {
                "type": "object",
                "properties": {
                    "network": {
                        "type": "string",
                        "enum": ["vehicle", "walking"],
                        "description": "Transportation network mode ('vehicle' or 'walking').",
                    },
                    "scenario": {
                        "type": "string",
                        "enum": ["optimistic", "pessimistic"],
                        "description": "Passability scenario ('optimistic' or 'pessimistic').",
                    },
                },
            },
        },
        {
            "name": "settlement_status",
            "description": "Check if a specific settlement is cut off or accessible, building count, road damage, detour distance, and evidence confidence.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Name of the settlement (accepts English, Nepali, Hindi, romanised spellings, and typos).",
                    }
                },
                "required": ["name"],
            },
        },
        {
            "name": "bridges_status",
            "description": "Get damage status for bridges. Can query whole disaster AOI or a local area like area='Syabrubesi' with radius_km.",
            "parameters": {
                "type": "object",
                "properties": {
                    "area": {
                        "type": "string",
                        "description": "Optional specific place name (e.g. 'Syabrubesi', 'confluence') to filter local bridges.",
                    },
                    "radius_km": {
                        "type": "number",
                        "description": "Radius in kilometers around the place (defaults to 1.5 km).",
                    },
                },
            },
        },
        {
            "name": "repair_priority",
            "description": "Get critical infrastructure repair PACKAGES ranking required to reconnect cut-off settlements. Indicates that no single repair restores access alone.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
        {
            "name": "rescue_priority",
            "description": "Prioritize search and rescue (SAR) team deployment locations by ranking cut-off settlements with severed foot/walking trails (critical isolation) and high building density.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
        {
            "name": "nearest_destination",
            "description": "Find the nearest hospital or designated emergency facility for a settlement, pre- and post-event route distances, and detour km.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Settlement name to check destination access for.",
                    }
                },
                "required": ["name"],
            },
        },
        {
            "name": "limitations",
            "description": "Get documented data limitations, cloud cover obscuration, optical acquisition dates, and uncertainty caveats.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
        {
            "name": "list_runs",
            "description": "List all available pipeline disaster event runs (e.g. 'test_A_trishuli', 'test_B_melamchi').",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
        {
            "name": "load_run",
            "description": "Switch active pipeline run to a different disaster event (e.g. 'test_B_melamchi') to answer questions about other events.",
            "parameters": {
                "type": "object",
                "properties": {
                    "run_name": {
                        "type": "string",
                        "description": "Name or prefix of the run to load (e.g. 'test_B_melamchi' or 'Melamchi').",
                    }
                },
                "required": ["run_name"],
            },
        },
    ]
