"""Tools callable by LLM / copilot to answer rescuer questions.

Each tool returns structured data strictly grounded in pipeline run outputs,
along with associated fact IDs for verification by the number guard.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple
from .facts import FactStore
from .names import PlaceNameResolver


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
    def damage_summary(self, area: Optional[str] = None) -> Dict[str, Any]:
        """Summarize damage across buildings, roads, and bridges."""
        fact_ids: List[str] = []

        # If specific area requested, try settlement status
        if area:
            settlement_res = self.settlement_status(area)
            if settlement_res.get("status") in ["exact", "fuzzy"]:
                return {
                    "tool": "damage_summary",
                    "area": area,
                    "area_settlement": settlement_res,
                    "fact_ids": settlement_res.get("fact_ids", []),
                }

        # Buildings
        b_tot = self.store.get("damage.buildings.total")
        b_aff = self.store.get("damage.buildings.affected_total")
        b_dest = self.store.get("damage.buildings.destroyed")
        b_dam = self.store.get("damage.buildings.damaged")
        b_poss = self.store.get("damage.buildings.possibly_damaged")
        b_not = self.store.get("damage.buildings.not_affected")
        b_cloud = self.store.get("damage.buildings.unknown_cloud")

        # Roads
        r_tot = self.store.get("damage.roads.total_km")
        r_dest = self.store.get("damage.roads.destroyed_km")
        r_poss = self.store.get("damage.roads.possibly_damaged_km")
        r_not = self.store.get("damage.roads.not_affected_km")
        r_cloud = self.store.get("damage.roads.unknown_cloud_km")

        # Bridges
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
    def bridges_status(self) -> Dict[str, Any]:
        """Summarize bridge damage and list destroyed bridges."""
        fact_ids: List[str] = []
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
            "total_bridges": self.store.get_value("damage.bridges.total", 0),
            "affected_total": self.store.get_value("damage.bridges.affected_total", 0),
            "destroyed_count": self.store.get_value("damage.bridges.destroyed", 0),
            "possibly_damaged_count": self.store.get_value("damage.bridges.possibly_damaged", 0),
            "not_affected_count": self.store.get_value("damage.bridges.not_affected", 0),
            "unknown_cloud_count": self.store.get_value("damage.bridges.unknown_cloud", 0),
            "destroyed_bridges_sample": destroyed_bridges[:5],
            "fact_ids": fact_ids,
        }

    # 6. Repair Priority
    def repair_priority(self) -> Dict[str, Any]:
        """
        Return greedy critical infrastructure repair prioritization.
        Identifies highest impact road/bridge segments to reconnect cut-off settlements.
        """
        fact_ids: List[str] = []
        steps = []
        for step_idx in range(1, 6):
            osm_f = self.store.get(f"repair.step_{step_idx}.osm_id")
            if osm_f is None:
                continue
            hwy_f = self.store.get(f"repair.step_{step_idx}.highway")
            len_f = self.store.get(f"repair.step_{step_idx}.length_m")
            set_f = self.store.get(f"repair.step_{step_idx}.settlements_reconnected")
            bld_f = self.store.get(f"repair.step_{step_idx}.buildings_reconnected")
            cum_set = self.store.get(f"repair.step_{step_idx}.cumulative_settlements")
            cum_bld = self.store.get(f"repair.step_{step_idx}.cumulative_buildings")

            for f in [osm_f, hwy_f, len_f, set_f, bld_f, cum_set, cum_bld]:
                if f is not None:
                    fact_ids.append(f.id)

            steps.append({
                "step": step_idx,
                "osm_id": osm_f.value if osm_f else "unknown",
                "highway": hwy_f.value if hwy_f else "unknown",
                "length_m": len_f.value if len_f else 0.0,
                "settlements_reconnected_step": set_f.value if set_f else 0,
                "buildings_reconnected_step": bld_f.value if bld_f else 0,
                "cumulative_settlements_reconnected": cum_set.value if cum_set else 0,
                "cumulative_buildings_reconnected": cum_bld.value if cum_bld else 0,
            })

        # Identify key bottleneck step
        top_impact = max(steps, key=lambda s: s["settlements_reconnected_step"]) if steps else None

        return {
            "tool": "repair_priority",
            "repair_steps": steps,
            "top_bottleneck_step": top_impact,
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
            "description": "Get breakdown of damaged buildings (destroyed, damaged, possibly damaged, cloud-covered), roads (km), and bridges.",
            "parameters": {
                "type": "object",
                "properties": {
                    "area": {
                        "type": "string",
                        "description": "Optional specific settlement or area name to focus damage query.",
                    }
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
            "description": "Get damage status for all bridges in the disaster zone, including destroyed and cloud-covered bridge counts.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
        {
            "name": "repair_priority",
            "description": "Get critical infrastructure repair prioritization ranking indicating which broken roads/bridges restore access to the most cut-off settlements.",
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
    ]
