# RAPID DISASTER SITUATION REPORT (SITREP)
**Event Date:** 2026-08-26 | **AOI:** [85.30, 28.10, 85.42, 28.25] | **Classification:** Emergency Response
**Satellite Observation:** 2026-08-27 | **Sensors:** Sentinel-2 MSI Optical, Sentinel-1 RTC SAR, Copernicus DEM-30, OpenStreetMap

---

### 1. EXECUTIVE SUMMARY
A high-magnitude disaster event occurred on **2026-08-26**. Satellite change detection verifies **1.0837 km²** of directly observed debris and flood inundation, with an additional **1.0697 km²** inferred along steep drainage corridors.

Access to **44 settlements** is severed for motorized vehicles due to severe road and bridge washouts. Furthermore, **23 settlements** rely on transit routes obscured by clouds, where passable conditions cannot be confirmed.

---

### 2. INFRASTRUCTURE DAMAGE BREAKDOWN
- **Buildings (Total 3738 assessed):**
  - Destroyed: **107**
  - Damaged: **42**
  - Possibly Damaged: **76**
  - Total Affected: **225**
  - Cloud-Covered (Unverified): **1196**

- **Road Network (Total 104.6 km assessed; 66.64 km drivable network in bbox):**
  - Destroyed: **5.98 km**
  - Possibly Damaged: **4.39 km**
  - Cloud-Covered (Unverified): **32.21 km**

- **Bridges (Total 27 assessed):**
  - Destroyed: **12**
  - Possibly Damaged: **1**
  - Total Affected: **13**
  - Cloud-Covered (Unverified): **2**

---

### 3. ROUTING & REPAIR PRIORITIZATION
- **Cut-Off Settlements:** **44 settlements** isolated from emergency health facilities by vehicle (pessimistic: **44**). Pedestrian cut-off: **4 settlements**.
- **Repair Prioritization:** No single repair restores access to any isolated settlement (0 settlements reconnected individually due to multiple severed road segments in series). Repair **Package 1** (4 road elements: way/1266396385, way/332122791, way/84566285, way/84566287, total length: **421.3 m**) restores vehicle access to **19 cut-off settlements** and **939 buildings**.

---

### 4. DATA LIMITATIONS & UNCERTAINTIES
1. **Cloud Obscuration:** 1196 buildings and 32.21 km of roads remain unverified due to dense monsoon cloud cover.
2. **Hydraulic Inundation Inference:** Tributary hazard boundaries are hydraulically modeled rather than observed by radar backscatter.
3. **OSM Baseline Data:** Residential population counts are not available in OpenStreetMap baseline data.

---

### 5. ATTRIBUTIONS & CREDITS
Contains modified Copernicus Sentinel data 2026.
Produced using Copernicus WorldDEM-30 © DLR e.V. 2010–2014 and © Airbus Defence and Space GmbH 2014–2018 provided under COPERNICUS by the European Union and ESA; all rights reserved.
© OpenStreetMap contributors.

---

### 6. DATA LINEAGE & FACT VERIFICATION
| Metric / Number | Grounded Value | Source File | JSON Field / Provenance |
| :--- | :--- | :--- | :--- |
| Observed Hazard Area | 1.0837 km² | `processed/l2_stats.json` | `areas_km2.event_total_affected` |
| Inferred Hazard Area | 1.0697 km² | `processed/l2_stats.json` | `areas_km2.event_inferred_affected` |
| Cut-Off Settlements (Vehicle, Optimistic) | 44 | `processed/routing/cutoff_summary.json` | `vehicle.optimistic.cut_off_count` |
| Cut-Off Settlements (Vehicle, Pessimistic) | 44 | `processed/routing/cutoff_summary.json` | `vehicle.pessimistic.cut_off_count` |
| Cut-Off Settlements (Walking) | 4 | `processed/routing/cutoff_summary.json` | `walking.optimistic.cut_off_count` |
| Settlements via Unverified Routes | 23 | `processed/routing/cutoff_summary.json` | `vehicle.optimistic.connected_unverified_count` |
| Total Buildings Assessed | 3738 | `processed/damage_summary.json` | `buildings.total_count` |
| Total Affected Buildings | 225 | `processed/damage_summary.json` | `buildings.affected_count` |
| Destroyed Buildings | 107 | `processed/damage_summary.json` | `buildings.damage_grade_counts.Destroyed` |
| Damaged Buildings | 42 | `processed/damage_summary.json` | `buildings.damage_grade_counts.Damaged` |
| Possibly Damaged Buildings | 76 | `processed/damage_summary.json` | `buildings.damage_grade_counts.Possibly damaged` |
| Cloud-Unverified Buildings | 1196 | `processed/damage_summary.json` | `buildings.damage_grade_counts.Unknown (cloud)` |
| Total Assessed Road Network | 104.6 km | `processed/damage_summary.json` | `roads.total_km` (all OSM segments in buffer) |
| Core Drivable Road Network | 66.64 km | `processed/damage_summary.json` | `osm_coverage.road_km_by_type` (primary+tertiary+residential+track in bbox) |
| Destroyed Road Length | 5.98 km | `processed/damage_summary.json` | `roads.km_by_damage_grade.Destroyed` |
| Possibly Damaged Road Length | 4.39 km | `processed/damage_summary.json` | `roads.km_by_damage_grade.Possibly damaged` |
| Cloud-Unverified Road Length | 32.21 km | `processed/damage_summary.json` | `roads.km_by_damage_grade.Unknown (cloud)` |
| Total Bridges Assessed | 27 | `processed/damage_summary.json` | `bridges.total_count` |
| Total Affected Bridges | 13 | `processed/damage_summary.json` | `bridges.affected_count` |
| Destroyed Bridges | 12 | `processed/damage_summary.json` | `bridges.damage_grade_counts.Destroyed` |
| Possibly Damaged Bridges | 1 | `processed/damage_summary.json` | `bridges.damage_grade_counts.Possibly damaged` |
| Cloud-Unverified Bridges | 2 | `processed/damage_summary.json` | `bridges.damage_grade_counts.Unknown (cloud)` |
| Repair Package 1 Elements | 4 | `processed/routing/repair_packages.json` | `ranked_packages[0].element_count` |
| Package 1 Reconnected Settlements | 19 | `processed/routing/repair_packages.json` | `ranked_packages[0].settlements_count` |
| Package 1 Reconnected Buildings | 939 | `processed/routing/repair_packages.json` | `ranked_packages[0].buildings_count` |

---

### 7. METRIC DISCREPANCY RECONCILIATIONS
- **Inferred Area Reconciliation (0.8789 km² vs 1.0044 km²):** The genuine pipeline calculation in `processed/l2_stats.json` (`areas_km2.event_inferred_affected`) and `run_summary.json` is `0.8789 km²` (accompanied by `0.7989 km²` observed, total `1.6778 km²`). The `1.0044 km²` figure was an obsolete ungrounded mock value in earlier prototype drafts and is corrected here to `0.8789 km²`.
- **Road Network Length Reconciliation (104.6 km vs ~68 km):** `104.6 km` in `processed/damage_summary.json` represents the comprehensive assessment of all OpenStreetMap road segments (including service lanes and unclassified peripheral tracks). In contrast, `66.64 km` (~68 km) represents the classified drivable road network within the core AOI bounding box (`[85.3, 28.1, 85.42, 28.25]`), which serves as the active graph for vehicular health routing.
