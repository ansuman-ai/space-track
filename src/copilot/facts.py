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
        """Extract all numeric values across all stored facts."""
        nums: Set[Union[int, float]] = set()
        for fact in self.facts.values():
            val = fact.value
            if isinstance(val, (int, float)) and not isinstance(val, bool):
                nums.add(val)
                if isinstance(val, float) and val.is_integer():
                    nums.add(int(val))
            elif isinstance(val, list):
                for item in val:
                    if isinstance(item, (int, float)) and not isinstance(item, bool):
                        nums.add(item)
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

        # 4. Repair Priority
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
                self.bridge_index[bid] = {
                    "bridge_id": bid,
                    "name": name,
                    "damage_grade": grade,
                    "evidence": ev,
                    "highway": props.get("highway"),
                    "distance_m": props.get("distance_m"),
                }
                self.add_fact(f"bridge.{clean_bid}.name", name, "name", src, "osm_baseline", event_date, f"Bridge name: {name}")
                self.add_fact(f"bridge.{clean_bid}.damage_grade", grade, "status", src, ev, optical_date, f"Damage grade for bridge {name}")

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
