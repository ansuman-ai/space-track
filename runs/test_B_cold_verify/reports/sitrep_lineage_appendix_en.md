# SITUATION REPORT — APPENDIX: DATA LINEAGE & AUDIT LOG
**Event Date:** 2021-06-15 | **AOI:** [85.53, 27.80, 85.62, 27.95] | **Run Directory:** `/home/zeus/Downloads/project1/runs/test_B_cold_verify`

This appendix provides field-by-field verification linking every fact in the 1-page Situation Report directly to authoritative pipeline JSON output files.

| Metric / Description | Verified Value | Source File | JSON Field / Provenance |
| :--- | :--- | :--- | :--- |
| Directly Observed Hazard Extent | 0.9 km² | `processed/l2_stats.json` | `areas_km2.event_total_affected` |
| Inferred Modelled Hazard Extent | 0.99 km² | `processed/l2_stats.json` | `areas_km2.event_inferred_affected` |
| Cut-Off Settlements (Vehicle, Optimistic) | 5 | `processed/routing/cutoff_summary.json` | `vehicle.optimistic.cut_off_count` |
| Cut-Off Settlements (Vehicle, Pessimistic) | 16 | `processed/routing/cutoff_summary.json` | `vehicle.pessimistic.cut_off_count` |
| Cut-Off Settlements (Walking) | 6 | `processed/routing/cutoff_summary.json` | `walking.optimistic.cut_off_count` |
| No Ground Access Settlements | 5 | `processed/routing/settlements.geojson` | `vehicle_status_opt == 'cut_off' and walking_status_opt == 'cut_off'` |
| Total Buildings Evaluated | 17492 | `processed/damage_summary.json` | `buildings.total_count` |
| Total Affected Buildings | 280 | `processed/damage_summary.json` | `buildings.affected_count` |
| Destroyed / Flooded Buildings | 72 | `processed/damage_summary.json` | `buildings.damage_grade_counts` |
| Damaged Buildings | 57 | `processed/damage_summary.json` | `buildings.damage_grade_counts` |
| Possibly Damaged Buildings | 151 | `processed/damage_summary.json` | `buildings.damage_grade_counts` |
| Cloud-Unverified Buildings | 9785 | `processed/damage_summary.json` | `buildings.damage_grade_counts.Unknown (cloud)` |
| Total Road Length Evaluated | 423.42 km | `processed/damage_summary.json` | `roads.total_km` (all OSM segments in buffer) |
| Classified Drivable Road Network | 133.15 km | `processed/damage_summary.json` | `osm_coverage.road_km_by_type` (in bbox) |
| Destroyed Road Length | 4.24 km | `processed/damage_summary.json` | `roads.km_by_damage_grade.Destroyed` |
| Possibly Damaged Road Length | 4.39 km | `processed/damage_summary.json` | `roads.km_by_damage_grade.Possibly damaged` |
| Cloud-Unverified Road Length | 246.52 km | `processed/damage_summary.json` | `roads.km_by_damage_grade.Unknown (cloud)` |
| Total Bridges Evaluated | 39 | `processed/damage_summary.json` | `bridges.total_count` |
| Total Affected Bridges | 11 | `processed/damage_summary.json` | `bridges.affected_count` |
| Destroyed / Flooded Bridges | 4 | `processed/damage_summary.json` | `bridges.damage_grade_counts` |
| Possibly Damaged Bridges | 7 | `processed/damage_summary.json` | `bridges.damage_grade_counts` |
| Cloud-Unverified Bridges | 18 | `processed/damage_summary.json` | `bridges.damage_grade_counts.Unknown (cloud)` |
| Repair Package 1 Elements | 1 | `processed/routing/repair_packages.json` | `ranked_packages[0].element_count` |
| Package 1 Reconnected Settlements | 2 | `processed/routing/repair_packages.json` | `ranked_packages[0].settlements_count` |
| Package 1 Reconnected Buildings | 17 | `processed/routing/repair_packages.json` | `ranked_packages[0].buildings_count` |

---
**Attributions & Lineage:**
Contains modified Copernicus Sentinel data 2021.
Produced using Copernicus WorldDEM-30 © DLR e.V. 2010–2014 and © Airbus Defence and Space GmbH 2014–2018 provided under COPERNICUS by the European Union and ESA; all rights reserved.
© OpenStreetMap contributors under ODbL.
European Union, Copernicus Emergency Management Service data (EMSR927, EMSR692, EMSR659).
Bountos et al., 2024 (Kuro Siwo).
Educational prototype, not an operational tool.
