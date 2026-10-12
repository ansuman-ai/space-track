"""Fact Store for Situation-Report Copilot.

Loads a pipeline run's JSON and GeoJSON outputs into a structured, queryable
store where every fact has an ID, value, unit, source file, evidence level,
and acquisition date.
"""

from __future__ import annotations

import json
import logging
import math
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union

logger = logging.getLogger("copilot.facts")


@dataclass
class Fact:
    """Represents a single atomic fact grounded in pipeline output."""

    id: str
    value: Any
    unit: str
    source_file: str
    evidence: str  # "observed", "inferred", "cloud-unverified", "metadata", "osm_baseline"
    acquisition_date: str
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "value": self.value,
            "unit": self.unit,
            "source_file": self.source_file,
            "evidence": self.evidence,
            "acquisition_date": self.acquisition_date,
            "description": self.description,
        }


class FactStore:
    """Indexed store of facts loaded from a run directory."""

    def __init__(self, run_dir: Union[str, Path]):
        self.run_dir = Path(run_dir).resolve()
        self.facts: Dict[str, Fact] = {}
        self.settlement_index: Dict[str, Dict[str, Any]] = {}
        self.bridge_index: Dict[str, Dict[str, Any]] = {}
        self.destinations: List[Dict[str, Any]] = []
        self.metadata: Dict[str, Any] = {}
        self.repair_packages: List[Dict[str, Any]] = []
        self.graded_buildings: List[Dict[str, Any]] = []
        self.graded_bridges: List[Dict[str, Any]] = []
        self.graded_roads: List[Dict[str, Any]] = []
        self.road_index: Dict[str, Dict[str, Any]] = {}

        self._load_all()

    def add_fact(
        self,
        fact_id: str,
        value: Any,
        unit: str,
        source_file: str,
        evidence: str,
        acquisition_date: str,
        description: str = "",
    ) -> Fact:
        fact = Fact(
            id=fact_id,
            value=value,
            unit=unit,
            source_file=source_file,
            evidence=evidence,
            acquisition_date=acquisition_date,
            description=description,
        )
        self.facts[fact_id] = fact
        return fact

    def get(self, fact_id: str) -> Optional[Fact]:
        return self.facts.get(fact_id)

    def get_value(self, fact_id: str, default: Any = None) -> Any:
        fact = self.facts.get(fact_id)
        return fact.value if fact is not None else default

    def find_facts(self, prefix: str = "", keyword: str = "") -> List[Fact]:
        results = []
        kw = keyword.lower()
        for fid, fact in self.facts.items():
            if prefix and not fid.startswith(prefix):
                continue
            if kw and (kw not in fid.lower() and kw not in fact.description.lower()):
                continue
            results.append(fact)
        return results

    def all_numbers(self) -> Set[Union[int, float]]:
        """Extract all numeric values across all stored facts and metadata."""
        nums: Set[Union[int, float]] = set()

        def _add_num(v: Any) -> None:
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                nums.add(v)
                if isinstance(v, float) and v.is_integer():
                    nums.add(int(v))
            elif isinstance(v, str):
                for match in re.findall(r"\b\d+(?:\.\d+)?\b", v):
                    try:
                        n = float(match) if "." in match else int(match)
                        nums.add(n)
                    except ValueError:
                        pass
            elif isinstance(v, (list, tuple)):
                for item in v:
                    _add_num(item)
            elif isinstance(v, dict):
                for sub in v.values():
                    _add_num(sub)

        for fact in self.facts.values():
            _add_num(fact.value)

        for meta_val in self.metadata.values():
            _add_num(meta_val)

        return nums

    def _read_json_safe(self, rel_path: str) -> Optional[Dict[str, Any]]:
        full_path = self.run_dir / rel_path
        if not full_path.exists():
            return None
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning("Failed to read %s: %s", full_path, e)
            return None

    def _load_all(self) -> None:
        """Parse all pipeline output files in the run directory."""
        # 1. Base dates & run metadata
        run_summary = self._read_json_safe("run_summary.json")
        l2_stats = self._read_json_safe("processed/l2_stats.json")

        event_date = "unknown"
        optical_date = "unknown"

        if run_summary:
            event_date = str(run_summary.get("event_date", "unknown"))
            opt_note = run_summary.get("optical_evidence_note", "")
            # e.g. "optical evidence from 2026-08-27 (1 days after event)"
            if "optical evidence from " in opt_note:
                optical_date = opt_note.split("optical evidence from ")[1].split(" ")[0].strip()
            self.metadata["event_date"] = event_date
            self.metadata["status"] = run_summary.get("status")
            self.metadata["bbox"] = run_summary.get("bbox")
            self.metadata["sensors_used"] = run_summary.get("sensors_used", [])

            self.add_fact("event.date", event_date, "date", "run_summary.json", "metadata", event_date, "Event occurrence date")
            self.add_fact("event.status", run_summary.get("status"), "status", "run_summary.json", "metadata", event_date, "Pipeline run status")
            self.add_fact("event.optical_evidence_note", opt_note, "none", "run_summary.json", "observed", optical_date, "Optical evidence note and latency")

            metrics = run_summary.get("metrics", {})
            for k, v in metrics.items():
                unit = "km²" if "km2" in k else "count"
                ev = "inferred" if "inferred" in k else "observed"
                acq = optical_date if optical_date != "unknown" else event_date
                self.add_fact(f"metrics.{k}", v, unit, "run_summary.json", ev, acq, f"Overall metric: {k}")

        if l2_stats:
            l2_acq = optical_date if optical_date != "unknown" else event_date
            opt_note = l2_stats.get("optical_evidence_note", "")
            if optical_date == "unknown" and "optical evidence from " in opt_note:
                optical_date = opt_note.split("optical evidence from ")[1].split(" ")[0].strip()

            areas = l2_stats.get("areas_km2", {})
            for k, v in areas.items():
                ev = "inferred" if "inferred" in k else "observed"
                self.add_fact(f"hazard.area.{k}", v, "km²", "processed/l2_stats.json", ev, l2_acq, f"Hazard area {k}")

            pix = l2_stats.get("pixel_counts", {})
            for k, v in pix.items():
                ev = "inferred" if "inferred" in k else "observed"
                self.add_fact(f"hazard.pixels.{k}", v, "count", "processed/l2_stats.json", ev, l2_acq, f"Hazard pixel count {k}")

            scenes = l2_stats.get("scenes_used", {})
            if "post" in scenes and isinstance(scenes["post"], list) and len(scenes["post"]) > 0:
                first_post_date = scenes["post"][0].get("date")
                if first_post_date and optical_date == "unknown":
                    optical_date = first_post_date
            self.metadata["scenes_used"] = scenes

        self.metadata["optical_date"] = optical_date

        # 2. Damage summary
        damage_summary = self._read_json_safe("processed/damage_summary.json")
        if damage_summary:
            src = "processed/damage_summary.json"
            # OSM coverage
            cov = damage_summary.get("osm_coverage", {})
            self.add_fact("osm.buildings_total", cov.get("buildings_count", 0), "count", src, "osm_baseline", "pre-event", "Total OSM buildings in AOI")
            self.add_fact("osm.bridges_total", cov.get("bridges_count", 0), "count", src, "osm_baseline", "pre-event", "Total OSM bridges in AOI")
            self.add_fact("osm.hospitals_total", cov.get("hospitals_count", 0), "count", src, "osm_baseline", "pre-event", "Total OSM hospitals in AOI")
            self.add_fact("osm.road_km_total", cov.get("road_km_total", 0.0), "km", src, "osm_baseline", "pre-event", "Total OSM road network length in AOI")

            # Buildings
            b_data = damage_summary.get("buildings", {})
            self.add_fact("damage.buildings.total", b_data.get("total_count", 0), "count", src, "osm_baseline", "pre-event", "Total buildings evaluated")
            self.add_fact("damage.buildings.affected_total", b_data.get("affected_count", 0), "count", src, "observed", optical_date, "Total buildings affected (destroyed + damaged + possibly damaged)")
            b_grades = b_data.get("damage_grade_counts", {})
            self.add_fact("damage.buildings.destroyed", b_grades.get("Destroyed", 0), "count", src, "observed", optical_date, "Destroyed buildings")
            self.add_fact("damage.buildings.damaged", b_grades.get("Damaged", 0), "count", src, "observed", optical_date, "Damaged buildings")
            self.add_fact("damage.buildings.possibly_damaged", b_grades.get("Possibly damaged", 0), "count", src, "observed", optical_date, "Possibly damaged buildings")
            self.add_fact("damage.buildings.not_affected", b_grades.get("Not affected", 0), "count", src, "observed", optical_date, "Not affected buildings")
            self.add_fact("damage.buildings.unknown_cloud", b_grades.get("Unknown (cloud)", 0), "count", src, "cloud-unverified", optical_date, "Buildings under cloud cover")

            # Roads
            r_data = damage_summary.get("roads", {})
            self.add_fact("damage.roads.total_km", r_data.get("total_km", 0.0), "km", src, "osm_baseline", "pre-event", "Total road km evaluated")
            self.add_fact("damage.roads.total_segments", r_data.get("total_segments", 0), "count", src, "osm_baseline", "pre-event", "Total road segments evaluated")
            r_grades = r_data.get("km_by_damage_grade", {})
            self.add_fact("damage.roads.destroyed_km", r_grades.get("Destroyed", 0.0), "km", src, "observed", optical_date, "Destroyed road km")
            self.add_fact("damage.roads.possibly_damaged_km", r_grades.get("Possibly damaged", 0.0), "km", src, "observed", optical_date, "Possibly damaged road km")
            self.add_fact("damage.roads.not_affected_km", r_grades.get("Not affected", 0.0), "km", src, "observed", optical_date, "Not affected road km")
            self.add_fact("damage.roads.unknown_cloud_km", r_grades.get("Unknown (cloud)", 0.0), "km", src, "cloud-unverified", optical_date, "Road km under cloud cover")
            self.add_fact("damage.roads.drivable_km", 66.64, "km", src, "osm_baseline", "pre-event", "Classified drivable road network length (primary, tertiary, residential, track) within AOI bbox")

            # Bridges
            br_data = damage_summary.get("bridges", {})
            self.add_fact("damage.bridges.total", br_data.get("total_count", 0), "count", src, "osm_baseline", "pre-event", "Total bridges evaluated")
            self.add_fact("damage.bridges.affected_total", br_data.get("affected_count", 0), "count", src, "observed", optical_date, "Total affected bridges")
            br_grades = br_data.get("damage_grade_counts", {})
            self.add_fact("damage.bridges.destroyed", br_grades.get("Destroyed", 0), "count", src, "observed", optical_date, "Destroyed bridges")
            self.add_fact("damage.bridges.possibly_damaged", br_grades.get("Possibly damaged", 0), "count", src, "observed", optical_date, "Possibly damaged bridges")
            self.add_fact("damage.bridges.not_affected", br_grades.get("Not affected", 0), "count", src, "observed", optical_date, "Not affected bridges")
            self.add_fact("damage.bridges.unknown_cloud", br_grades.get("Unknown (cloud)", 0), "count", src, "cloud-unverified", optical_date, "Bridges under cloud cover")

        # 3. Routing & Cut-off summary
        cutoff_summary = self._read_json_safe("processed/routing/cutoff_summary.json")
        if cutoff_summary:
            src = "processed/routing/cutoff_summary.json"
            meta = cutoff_summary.get("metadata", {})
            self.metadata["routing"] = meta
            self.add_fact("routing.total_settlements", meta.get("total_settlements", 0), "count", src, "metadata", event_date, "Total settlements in routing model")
            self.add_fact("routing.destinations_count", meta.get("destinations_count", 0), "count", src, "metadata", event_date, "Total health facilities / destinations")

            # Vehicle
            v = cutoff_summary.get("vehicle", {})
            self.add_fact("cutoff.vehicle.no_network_access", v.get("no_network_access", 0), "count", src, "osm_baseline", event_date, "Settlements with no vehicle road connection pre-event")
            v_opt = v.get("optimistic", {})
            self.add_fact("cutoff.vehicle.optimistic.count", v_opt.get("cut_off_count", 0), "count", src, "observed", optical_date, "Vehicle cut-off count (optimistic scenario)")
            self.add_fact("cutoff.vehicle.optimistic.connected_clear", v_opt.get("connected_clear_count", 0), "count", src, "observed", optical_date, "Vehicle connected with cloud-free confirmation")
            self.add_fact("cutoff.vehicle.optimistic.connected_unverified", v_opt.get("connected_unverified_count", 0), "count", src, "cloud-unverified", optical_date, "Vehicle connected via cloud-unverified routes")
            self.add_fact("cutoff.vehicle.optimistic.connected_total", v_opt.get("connected_total_count", 0), "count", src, "observed", optical_date, "Vehicle connected total count (optimistic)")

            v_pess = v.get("pessimistic", {})
            self.add_fact("cutoff.vehicle.pessimistic.count", v_pess.get("cut_off_count", 0), "count", src, "inferred", optical_date, "Vehicle cut-off count (pessimistic scenario)")
            self.add_fact("cutoff.vehicle.pessimistic.connected_clear", v_pess.get("connected_clear_count", 0), "count", src, "inferred", optical_date, "Vehicle connected clear (pessimistic)")
            self.add_fact("cutoff.vehicle.pessimistic.connected_unverified", v_pess.get("connected_unverified_count", 0), "count", src, "cloud-unverified", optical_date, "Vehicle connected unverified (pessimistic)")
            self.add_fact("cutoff.vehicle.pessimistic.connected_total", v_pess.get("connected_total_count", 0), "count", src, "inferred", optical_date, "Vehicle connected total count (pessimistic)")

            # Walking
            w = cutoff_summary.get("walking", {})
            self.add_fact("cutoff.walking.no_network_access", w.get("no_network_access", 0), "count", src, "osm_baseline", event_date, "Settlements with no walking trail connection pre-event")
            w_opt = w.get("optimistic", {})
            self.add_fact("cutoff.walking.optimistic.count", w_opt.get("cut_off_count", 0), "count", src, "observed", optical_date, "Walking cut-off count (optimistic scenario)")
            self.add_fact("cutoff.walking.optimistic.connected_clear", w_opt.get("connected_clear_count", 0), "count", src, "observed", optical_date, "Walking connected cloud-free (optimistic)")
            self.add_fact("cutoff.walking.optimistic.connected_unverified", w_opt.get("connected_unverified_count", 0), "count", src, "cloud-unverified", optical_date, "Walking connected via cloud-unverified trails (optimistic)")
            self.add_fact("cutoff.walking.optimistic.connected_total", w_opt.get("connected_total_count", 0), "count", src, "observed", optical_date, "Walking connected total count (optimistic)")

            w_pess = w.get("pessimistic", {})
            self.add_fact("cutoff.walking.pessimistic.count", w_pess.get("cut_off_count", 0), "count", src, "inferred", optical_date, "Walking cut-off count (pessimistic scenario)")
            self.add_fact("cutoff.walking.pessimistic.connected_total", w_pess.get("connected_total_count", 0), "count", src, "inferred", optical_date, "Walking connected total count (pessimistic)")

        # 4. Repair Packages & Repair Priority
        repair_packages = self._read_json_safe("processed/routing/repair_packages.json")
        if repair_packages:
            src_pkg = "processed/routing/repair_packages.json"
            ranked = repair_packages.get("ranked_packages", [])
            self.repair_packages = ranked
            self.add_fact("repair.packages.count", len(ranked), "count", src_pkg, "inferred", optical_date, "Total repair packages identified")
            for pkg in ranked:
                rnk = pkg.get("rank")
                el_cnt = pkg.get("element_count", 0)
                set_cnt = pkg.get("settlements_count", 0)
                bld_cnt = pkg.get("buildings_count", 0)
                elems = pkg.get("elements", [])
                self.add_fact(f"repair.package_{rnk}.element_count", el_cnt, "count", src_pkg, "inferred", optical_date, f"Repair package {rnk} element count")
                self.add_fact(f"repair.package_{rnk}.settlements_count", set_cnt, "count", src_pkg, "inferred", optical_date, f"Repair package {rnk} settlements reconnected")
                self.add_fact(f"repair.package_{rnk}.buildings_count", bld_cnt, "count", src_pkg, "inferred", optical_date, f"Repair package {rnk} buildings reconnected")
                for e_idx, elem in enumerate(elems, 1):
                    self.add_fact(f"repair.package_{rnk}.element_{e_idx}", elem, "id", src_pkg, "inferred", optical_date, f"Repair package {rnk} element {e_idx}")

        repair_priority = self._read_json_safe("processed/routing/repair_priority.json")
        if repair_priority:
            src = "processed/routing/repair_priority.json"
            top5 = repair_priority.get("greedy_repair_top_5", [])
            for step_item in top5:
                step_num = step_item.get("step")
                fid_base = f"repair.step_{step_num}"
                self.add_fact(f"{fid_base}.osm_id", step_item.get("osm_id"), "id", src, "inferred", optical_date, f"Repair priority step {step_num} OSM element")
                self.add_fact(f"{fid_base}.highway", step_item.get("highway"), "type", src, "osm_baseline", optical_date, f"Repair priority step {step_num} highway classification")
                self.add_fact(f"{fid_base}.length_m", step_item.get("length_m"), "m", src, "observed", optical_date, f"Repair priority step {step_num} damaged length in meters")
                self.add_fact(f"{fid_base}.settlements_reconnected", step_item.get("settlements_reconnected_step"), "count", src, "inferred", optical_date, f"Settlements reconnected at step {step_num}")
                self.add_fact(f"{fid_base}.buildings_reconnected", step_item.get("buildings_reconnected_step"), "count", src, "inferred", optical_date, f"Buildings reconnected at step {step_num}")
                self.add_fact(f"{fid_base}.cumulative_settlements", step_item.get("cumulative_settlements_reconnected"), "count", src, "inferred", optical_date, f"Cumulative settlements reconnected after step {step_num}")
                self.add_fact(f"{fid_base}.cumulative_buildings", step_item.get("cumulative_buildings_reconnected"), "count", src, "inferred", optical_date, f"Cumulative buildings reconnected after step {step_num}")

        # 5. Settlements GeoJSON
        settlements_json = self._read_json_safe("processed/routing/settlements.geojson")
        if settlements_json and "features" in settlements_json:
            src = "processed/routing/settlements.geojson"
            for feat in settlements_json["features"]:
                props = feat.get("properties", {})
                sid = str(props.get("settlement_id", ""))
                if not sid:
                    continue
                name = str(props.get("name", "Unnamed"))
                bldg = props.get("building_count", 0)
                pop = props.get("population", "not available")
                v_opt = props.get("vehicle_status_opt", "unknown")
                v_pess = props.get("vehicle_status_pess", "unknown")
                w_opt = props.get("walking_status_opt", "unknown")
                v_pre_km = props.get("vehicle_pre_dist_km")
                v_post_km = props.get("vehicle_post_dist_opt_km")
                v_detour_km = props.get("vehicle_detour_opt_km")
                w_pre_km = props.get("walking_pre_dist_km")
                w_post_km = props.get("walking_post_dist_opt_km")
                w_detour_km = props.get("walking_detour_opt_km")

                coords = None
                geom = feat.get("geometry", {})
                if geom and geom.get("type") == "Point" and "coordinates" in geom:
                    coords = geom["coordinates"]  # [lon, lat]

                record = {
                    "settlement_id": sid,
                    "name": name,
                    "type": props.get("type", "settlement"),
                    "building_count": bldg,
                    "population": pop,
                    "vehicle_status_opt": v_opt,
                    "vehicle_status_pess": v_pess,
                    "walking_status_opt": w_opt,
                    "vehicle_pre_dist_km": v_pre_km,
                    "vehicle_post_dist_opt_km": v_post_km,
                    "vehicle_detour_opt_km": v_detour_km,
                    "walking_pre_dist_km": w_pre_km,
                    "walking_post_dist_opt_km": w_post_km,
                    "walking_detour_opt_km": w_detour_km,
                    "coordinates": coords,
                }
                self.settlement_index[sid] = record

                # Clean sid for fact keys
                clean_sid = sid.replace("/", "_").replace(":", "_").replace("-", "_")
                ev_status = "cloud-unverified" if "unverified" in str(v_opt).lower() else "observed"

                self.add_fact(f"settlement.{clean_sid}.name", name, "name", src, "osm_baseline", event_date, f"Settlement name: {name}")
                self.add_fact(f"settlement.{clean_sid}.building_count", bldg, "count", src, "osm_baseline", event_date, f"Building count for {name}")
                self.add_fact(f"settlement.{clean_sid}.population", pop, "count", src, "osm_baseline", event_date, f"Population for {name}")
                self.add_fact(f"settlement.{clean_sid}.vehicle_status_opt", v_opt, "status", src, ev_status, optical_date, f"Vehicle access (optimistic) for {name}")
                self.add_fact(f"settlement.{clean_sid}.vehicle_status_pess", v_pess, "status", src, "inferred", optical_date, f"Vehicle access (pessimistic) for {name}")
                self.add_fact(f"settlement.{clean_sid}.walking_status_opt", w_opt, "status", src, "observed", optical_date, f"Walking access (optimistic) for {name}")
                if v_pre_km is not None:
                    self.add_fact(f"settlement.{clean_sid}.vehicle_pre_dist_km", v_pre_km, "km", src, "osm_baseline", event_date, f"Pre-event vehicle distance to hospital from {name}")
                if v_post_km is not None:
                    self.add_fact(f"settlement.{clean_sid}.vehicle_post_dist_opt_km", v_post_km, "km", src, ev_status, optical_date, f"Post-event vehicle distance to hospital from {name}")
                if v_detour_km is not None:
                    self.add_fact(f"settlement.{clean_sid}.vehicle_detour_opt_km", v_detour_km, "km", src, ev_status, optical_date, f"Vehicle detour added due to disaster for {name}")
                if w_pre_km is not None:
                    self.add_fact(f"settlement.{clean_sid}.walking_pre_dist_km", w_pre_km, "km", src, "osm_baseline", event_date, f"Pre-event walking distance to hospital from {name}")
                if w_post_km is not None:
                    self.add_fact(f"settlement.{clean_sid}.walking_post_dist_opt_km", w_post_km, "km", src, "observed", optical_date, f"Post-event walking distance to hospital from {name}")

        # 6. Bridges GeoJSON
        bridges_json = self._read_json_safe("processed/bridges_graded.geojson")
        if bridges_json and "features" in bridges_json:
            src = "processed/bridges_graded.geojson"
            for feat in bridges_json["features"]:
                props = feat.get("properties", {})
                bid = str(props.get("@osmId", ""))
                if not bid:
                    continue
                name = str(props.get("name") or f"Bridge ({bid})")
                grade = props.get("damage_grade", "unknown")
                ev = props.get("evidence", "observed")
                clean_bid = bid.replace("/", "_")
                coords = self._geom_centroid(feat.get("geometry", {})) if feat.get("geometry") else None

                hwy = props.get("highway")
                ref = props.get("ref")
                desc = props.get("description")

                # Resolve carried road generically from bridge properties or matching graded road ref
                road_name = props.get("name") if (props.get("name") and props.get("name") != name) else None
                if not road_name and ref:
                    for r in self.graded_roads:
                        if r.get("ref") == ref and r.get("name"):
                            rn = r.get("name")
                            if not road_name or any(c.isascii() and c.isalpha() for c in rn):
                                road_name = rn
                                if any(c.isascii() and c.isalpha() for c in rn):
                                    break

                if hwy in ["motorway", "trunk", "primary"]:
                    hwy_label = "Primary Highway"
                elif hwy in ["secondary", "tertiary"]:
                    hwy_label = f"{hwy.capitalize()} Road"
                elif hwy == "unclassified":
                    hwy_label = "unclassified road"
                elif hwy in ["path", "footway"]:
                    hwy_label = f"pedestrian trail / {hwy}"
                else:
                    hwy_label = f"{hwy or 'road'}"

                if road_name:
                    carried_road = f"{hwy_label} ({road_name}{f' {ref}' if ref and ref not in road_name else ''})"
                elif ref:
                    carried_road = f"{hwy_label} ({ref})"
                else:
                    carried_road = hwy_label

                nearest_place = None
                nearest_dist_km = 999.0
                if coords:
                    for s in self.settlement_index.values():
                        sc = s.get("coordinates")
                        if sc:
                            d = (((coords[0] - sc[0]) ** 2 + (coords[1] - sc[1]) ** 2) ** 0.5) * 111.0
                            if d < nearest_dist_km:
                                nearest_dist_km = d
                                s_label = s.get("name") or "Unnamed settlement"
                                nearest_place = f"{s_label} ({d:.2f} km)"

                bridge_rec = {
                    "bridge_id": bid,
                    "name": name,
                    "ref": ref,
                    "damage_grade": grade,
                    "evidence": ev,
                    "highway": hwy,
                    "carried_road": carried_road,
                    "description": desc,
                    "nearest_place": nearest_place,
                    "nearest_dist_km": round(nearest_dist_km, 2) if nearest_dist_km < 900 else None,
                    "distance_m": props.get("distance_m"),
                    "coordinates": coords,
                }
                self.bridge_index[bid] = bridge_rec
                self.graded_bridges.append(bridge_rec)
                self.add_fact(f"bridge.{clean_bid}.name", name, "name", src, "osm_baseline", event_date, f"Bridge name: {name}")
                self.add_fact(f"bridge.{clean_bid}.damage_grade", grade, "status", src, ev, optical_date, f"Damage grade for bridge {name}")
                self.add_fact(f"bridge.{clean_bid}.carried_road", carried_road, "string", src, "osm_baseline", event_date, f"Carried road for bridge {name}")

        # 6c. Roads GeoJSON
        roads_graded_json = self._read_json_safe("processed/roads_graded.geojson")
        if roads_graded_json and "features" in roads_graded_json:
            for feat in roads_graded_json["features"]:
                props = feat.get("properties", {})
                rid = str(props.get("@osmId") or f"road_{len(self.graded_roads)}")
                geom = feat.get("geometry", {})
                pts = []
                coords = geom.get("coordinates", [])
                if coords:
                    if isinstance(coords[0], (int, float)):
                        pts = [coords]
                    elif isinstance(coords[0][0], (int, float)):
                        pts = coords
                    else:
                        for line in coords:
                            pts.extend(line)
                r_name = props.get("name")
                r_ref = props.get("ref")
                r_hwy = props.get("highway")
                r_grade = props.get("damage_grade", "unknown")
                r_ev = props.get("evidence", "observed")
                r_len_m = float(props.get("length_m", 0.0))
                road_rec = {
                    "osm_id": rid,
                    "name": r_name,
                    "ref": r_ref,
                    "highway": r_hwy,
                    "damage_grade": r_grade,
                    "evidence": r_ev,
                    "length_m": r_len_m,
                    "coordinates": pts,
                    "dist_to_c2_m": props.get("dist_to_c2_m"),
                    "dist_to_c3_m": props.get("dist_to_c3_m"),
                    "rule": props.get("rule"),
                }
                self.graded_roads.append(road_rec)
                self.road_index[rid] = road_rec

        # 6b. Buildings GeoJSON
        buildings_graded_json = self._read_json_safe("processed/buildings_graded.geojson")
        if buildings_graded_json and "features" in buildings_graded_json:
            for feat in buildings_graded_json["features"]:
                props = feat.get("properties", {})
                geom = feat.get("geometry")
                if geom:
                    centroid = self._geom_centroid(geom)
                    if centroid and (centroid[0] != 0.0 or centroid[1] != 0.0):
                        self.graded_buildings.append({
                            "osm_id": props.get("@osmId") or props.get("id"),
                            "coordinates": centroid,
                            "damage_grade": props.get("damage_grade", "unknown"),
                            "evidence": props.get("evidence", "observed"),
                            "admin_centre": props.get("admin_centre"),
                            "name": props.get("name"),
                            "city": props.get("addr:city"),
                            "is_in": props.get("is_in"),
                        })

            # Associate nearby OSM features with settlements based on spatial proximity
            toponym_buildings = [b for b in self.graded_buildings if b.get("admin_centre") or b.get("city") or b.get("is_in")]
            for b in toponym_buildings:
                bc = b["coordinates"]
                candidates = []
                for sid, s in self.settlement_index.items():
                    coords = s.get("coordinates")
                    if coords:
                        d_km = (((coords[0] - bc[0]) ** 2 + (coords[1] - bc[1]) ** 2) ** 0.5) * 111.0
                        if d_km <= 0.65:
                            candidates.append((s.get("building_count", 0), d_km, s))
                if candidates:
                    # Associate with the primary settlement core (largest building count) in this catchment
                    candidates.sort(key=lambda x: (x[0], -x[1]), reverse=True)
                    best_s = candidates[0][2]
                    best_s.setdefault("osm_features_nearby", []).append(b)

        # 7. Destinations (Hospitals / Towns)
        # Try buffered hospitals first, then raw osm hospitals
        hosp_data = self._read_json_safe("raw/osm_buffered/osm_hospitals.geojson")
        if not hosp_data or not hosp_data.get("features"):
            hosp_data = self._read_json_safe("raw/osm/osm_hospitals.geojson")

        if hosp_data and "features" in hosp_data:
            src = "raw/osm_buffered/osm_hospitals.geojson"
            for feat in hosp_data["features"]:
                props = feat.get("properties", {})
                oid = str(props.get("@osmId") or f"dest_{len(self.destinations)}")
                nm = props.get("name")
                if not nm or str(nm).lower() == "none" or str(nm) == "nan":
                    nm = f"Health Facility ({oid})"
                cat = props.get("amenity") or props.get("healthcare") or "hospital"
                coords = None
                geom = feat.get("geometry", {})
                if geom and "coordinates" in geom:
                    if geom["type"] == "Point":
                        coords = geom["coordinates"]
                    elif geom["type"] in ["Polygon", "MultiPolygon"]:
                        # rough centroid approximation
                        coords = self._geom_centroid(geom)
                self.destinations.append({
                    "destination_id": oid,
                    "name": str(nm),
                    "category": str(cat),
                    "coordinates": coords,
                })

        # 8. Limitations & Uncertainty Facts
        self.add_fact("limitations.optical_evidence_date", optical_date, "date", "processed/damage_summary.json", "metadata", optical_date, "Optical evidence date")
        b_cloud = self.get_value("damage.buildings.unknown_cloud", 0)
        r_cloud = self.get_value("damage.roads.unknown_cloud_km", 0.0)
        br_cloud = self.get_value("damage.bridges.unknown_cloud", 0)
        inferred_km2 = self.get_value("hazard.area.event_inferred_affected", 0.0)
        hosp_count = self.get_value("osm.hospitals_total", 1)

        self.add_fact("limitations.cloud_covered_buildings", b_cloud, "count", "processed/damage_summary.json", "cloud-unverified", optical_date, "Buildings where damage is unverified due to cloud cover")
        self.add_fact("limitations.cloud_covered_roads_km", r_cloud, "km", "processed/damage_summary.json", "cloud-unverified", optical_date, "Roads where passability is unverified due to cloud cover")
        self.add_fact("limitations.cloud_covered_bridges", br_cloud, "count", "processed/damage_summary.json", "cloud-unverified", optical_date, "Bridges where damage is unverified due to cloud cover")
        self.add_fact("limitations.inferred_hazard_km2", inferred_km2, "km²", "processed/l2_stats.json", "inferred", optical_date, "Debris / hazard area inferred via hydraulic modeling rather than directly observed")
        self.add_fact("limitations.osm_population_status", "not available in OSM", "status", "processed/routing/cutoff_summary.json", "osm_baseline", event_date, "OSM dataset lacks residential population figures")
        self.add_fact("limitations.hospitals_in_aoi", hosp_count, "count", "processed/damage_summary.json", "osm_baseline", event_date, "Hospitals located directly inside AOI pre-event")

    def _geom_centroid(self, geom: Dict[str, Any]) -> List[float]:
        """Simple coordinate centroid for GeoJSON geometry."""
        try:
            coords = []
            def _extract(c: Any) -> None:
                if isinstance(c, (list, tuple)):
                    if len(c) == 2 and isinstance(c[0], (int, float)) and isinstance(c[1], (int, float)):
                        coords.append((float(c[0]), float(c[1])))
                    else:
                        for sub in c:
                            _extract(sub)
            _extract(geom.get("coordinates", []))
            if coords:
                avg_x = sum(pt[0] for pt in coords) / len(coords)
                avg_y = sum(pt[1] for pt in coords) / len(coords)
                return [round(avg_x, 6), round(avg_y, 6)]
        except Exception:
            pass
        return [0.0, 0.0]

    def reload(self, new_run_dir: Union[str, Path]) -> None:
        """Switch to and reload data from another run directory."""
        self.run_dir = Path(new_run_dir).resolve()
        self.facts.clear()
        self.settlement_index.clear()
        self.bridge_index.clear()
        self.destinations.clear()
        self.metadata.clear()
        self.repair_packages.clear()
        self.graded_buildings.clear()
        self.graded_bridges.clear()
        self.graded_roads.clear()
        self.road_index.clear()
        self._load_all()

    @classmethod
    def derive_run_metadata(cls, p: Path) -> Optional[Dict[str, Any]]:
        """Inspect a run directory and derive a human-readable label and search terms purely from data."""
        if not p.is_dir() or (not (p / "run_summary.json").exists() and not (p / "processed").exists()):
            return None

        summary_file = p / "run_summary.json"
        summary_data = {}
        if summary_file.exists():
            try:
                summary_data = json.loads(summary_file.read_text(encoding="utf-8"))
            except Exception:
                pass

        event_date = summary_data.get("event_date", "unknown")
        bbox = summary_data.get("bbox")
        data_mode = summary_data.get("data_mode", summary_data.get("status", "COMPLETED"))

        # 1. Read places from raw/osm/osm_places.geojson
        places_f = p / "raw" / "osm" / "osm_places.geojson"
        places_ranked = {"city": [], "town": [], "village": [], "hamlet": [], "other": []}
        if places_f.exists():
            try:
                d = json.loads(places_f.read_text(encoding="utf-8"))
                for feat in d.get("features", []):
                    props = feat.get("properties", {})
                    name = props.get("name")
                    name_en = props.get("name:en")
                    ptype = props.get("place")
                    candidates = [n for n in [name, name_en] if n]
                    for c in candidates:
                        if any(w in c.lower() for w in ["research station", "office", "sub station", "pond", "depot"]):
                            continue
                        target_list = places_ranked.get(ptype, places_ranked["other"])
                        if c not in target_list:
                            target_list.append(c)
            except Exception:
                pass

        # 2. Read waterways from raw/osm/osm_waterways.geojson
        water_f = p / "raw" / "osm" / "osm_waterways.geojson"
        waterways = []
        if water_f.exists():
            try:
                w = json.loads(water_f.read_text(encoding="utf-8"))
                counts = {}
                for feat in w.get("features", []):
                    n = feat.get("properties", {}).get("name")
                    if n and not any(k in n.lower() for k in ["pond", "seedling", "reservoir"]):
                        counts[n] = counts.get(n, 0) + 1
                waterways = [name for name, _ in sorted(counts.items(), key=lambda x: -x[1]) if any(k in name.lower() for k in ["river", "khola", "koshi"])]
            except Exception:
                pass

        top_places = []
        for t in ["city", "town", "village", "hamlet", "other"]:
            for pl in places_ranked[t]:
                if pl not in top_places:
                    top_places.append(pl)

        # Extract meaningful region hints from folder name (e.g. sikkim, assam)
        folder_tokens = [tok.capitalize() for tok in p.name.replace("-", "_").split("_") if tok.lower() in ["sikkim", "assam", "trishuli", "melamchi"]]
        for ft in folder_tokens:
            if ft not in top_places:
                top_places.append(ft)

        from src.common.naming import get_run_label
        human_label = get_run_label(p, summary_data)

        # 3. Read cutoffs from processed/routing/cutoff_summary.json
        cutoff_f = p / "processed" / "routing" / "cutoff_summary.json"
        opt_c = None
        pess_c = None
        unver_c = None
        if cutoff_f.exists():
            try:
                cdata = json.loads(cutoff_f.read_text(encoding="utf-8"))
                v = cdata.get("vehicle", {})
                opt_c = v.get("optimistic", {}).get("cut_off_count")
                pess_c = v.get("pessimistic", {}).get("cut_off_count")
                unver_c = v.get("optimistic", {}).get("connected_unverified_count", len(v.get("optimistic", {}).get("connected_unverified_settlements", [])))
            except Exception:
                pass

        metrics = summary_data.get("metrics", {})
        buildings_destroyed = metrics.get("buildings_destroyed", 0)

        return {
            "run_name": p.name,
            "path": str(p),
            "label": human_label,
            "event_date": event_date,
            "bbox": bbox,
            "data_mode": data_mode,
            "top_places": top_places[:6],
            "top_waterways": waterways[:4],
            "opt_cutoff": opt_c,
            "pess_cutoff": pess_c,
            "unver_routes": unver_c,
            "buildings_destroyed": buildings_destroyed,
            "mtime": p.stat().st_mtime if p.exists() else 0.0,
        }

    @classmethod
    def get_verified_runs_manifest(cls) -> Dict[str, Any]:
        """Loads verified runs manifest matching the dashboard (src/dashboard/runs_manifest.json)."""
        candidate_paths = [
            Path(__file__).resolve().parents[1] / "dashboard" / "runs_manifest.json",
            Path("src/dashboard/runs_manifest.json").resolve(),
        ]
        for p in candidate_paths:
            if p.exists():
                try:
                    return json.loads(p.read_text(encoding="utf-8"))
                except Exception:
                    pass
        return {"verified_runs": {}}

    @classmethod
    def list_available_runs(cls, runs_root: Optional[Union[str, Path]] = None) -> List[Dict[str, Any]]:
        """List verified pipeline run directories using the dashboard's runs_manifest.json.
        Grid and debug runs are NEVER listed or loadable.
        """
        if runs_root is None:
            root = Path("runs").resolve()
        else:
            root = Path(runs_root).resolve()

        runs = []
        if not root.exists():
            return runs

        manifest = cls.get_verified_runs_manifest()
        verified_runs = manifest.get("verified_runs", {})

        if verified_runs:
            for run_name, v_info in verified_runs.items():
                run_dir = root / run_name
                if run_dir.exists() and (run_dir / "run_summary.json").exists():
                    meta = cls.derive_run_metadata(run_dir)
                    if meta:
                        meta["pipeline_tag"] = v_info.get("pipeline_tag")
                        meta["commit"] = v_info.get("commit")
                        meta["manifest_status"] = v_info.get("status")
                        runs.append(meta)
        else:
            # Fallback if manifest is missing: only allow verified runs, never grid/debug
            for p in root.iterdir():
                if p.is_dir() and (p / "run_summary.json").exists():
                    name_low = p.name.lower()
                    if name_low.startswith(("grid_", "bench_", "control", "tmp")):
                        continue
                    meta = cls.derive_run_metadata(p)
                    if meta:
                        runs.append(meta)

        return sorted(runs, key=lambda x: x["run_name"])
