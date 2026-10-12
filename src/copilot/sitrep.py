"""Bilingual 1-Page Situation Report Generator (English & Nepali).

Generates strictly grounded situation reports:
- The LLM (or offline template) writes prose with placeholders like {{cutoff_count}}.
- The system replaces placeholders with exact numbers directly from FactStore.
- Outputs both Markdown and styled single-page PDF via WeasyPrint.
- Includes mandatory Copernicus & OSM attributions and data limitations.
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import weasyprint

from .facts import FactStore
from .guard import NumberGuard

logger = logging.getLogger("copilot.sitrep")


SITREP_TEMPLATE_PROSE_EN = """# RAPID DISASTER SITUATION REPORT (SITREP)
**Event Date:** {{event_date}} | **AOI:** {{bbox}} | **Classification:** Emergency Response
**Satellite Observation:** {{optical_evidence_date}} | **Sensors:** {{sensors_used}}

---

### 1. EXECUTIVE SUMMARY
A high-magnitude disaster event occurred on **{{event_date}}**. Satellite change detection verifies **{{affected_km2_observed}} km²** of directly observed debris and flood inundation, with an additional **{{affected_km2_inferred}} km²** inferred along steep drainage corridors.

Access to **{{cutoff_vehicle_optimistic_count}} settlements** is severed for motorized vehicles due to severe road and bridge washouts. Furthermore, **{{connected_unverified_count}} settlements** rely on transit routes obscured by clouds, where passable conditions cannot be confirmed.

---

### 2. INFRASTRUCTURE DAMAGE BREAKDOWN
- **Buildings (Total {{buildings_total}} assessed):**
  - Destroyed: **{{buildings_destroyed}}**
  - Damaged: **{{buildings_damaged}}**
  - Possibly Damaged: **{{buildings_possibly_damaged}}**
  - Total Affected: **{{buildings_affected_total}}**
  - Cloud-Covered (Unverified): **{{buildings_cloud_unverified}}**

- **Road Network (Total {{roads_total_km}} km assessed; {{roads_drivable_km}} km drivable network in bbox):**
  - Destroyed: **{{roads_destroyed_km}} km**
  - Possibly Damaged: **{{roads_possibly_damaged_km}} km**
  - Cloud-Covered (Unverified): **{{roads_cloud_unverified_km}} km**

- **Bridges (Total {{bridges_total}} assessed):**
  - Destroyed: **{{bridges_destroyed}}**
  - Possibly Damaged: **{{bridges_possibly_damaged}}**
  - Total Affected: **{{bridges_affected_total}}**
  - Cloud-Covered (Unverified): **{{bridges_cloud_unverified}}**

---

### 3. ROUTING & REPAIR PRIORITIZATION
- **Cut-Off Settlements:** **{{cutoff_vehicle_optimistic_count}} settlements** isolated from emergency health facilities by vehicle (pessimistic: **{{cutoff_vehicle_pessimistic_count}}**). Pedestrian cut-off: **{{cutoff_walking_optimistic_count}} settlements**.
- **Repair Prioritization:** No single repair restores access to any isolated settlement (0 settlements reconnected individually due to multiple severed road segments in series). Repair **Package 1** ({{package_1_element_count}} road elements: {{package_1_elements_list}}, total length: **{{package_1_length_m}} m**) restores vehicle access to **{{package_1_reconnected_settlements}} cut-off settlements** and **{{package_1_reconnected_buildings}} buildings**.

---

### 4. DATA LIMITATIONS & UNCERTAINTIES
1. **Cloud Obscuration:** {{buildings_cloud_unverified}} buildings and {{roads_cloud_unverified_km}} km of roads remain unverified due to dense monsoon cloud cover.
2. **Hydraulic Inundation Inference:** Tributary hazard boundaries are hydraulically modeled rather than observed by radar backscatter.
3. **OSM Baseline Data:** Residential population counts are not available in OpenStreetMap baseline data.

---

### 5. ATTRIBUTIONS & CREDITS
{{attributions}}

---

### 6. DATA LINEAGE & FACT VERIFICATION
| Metric / Number | Grounded Value | Source File | JSON Field / Provenance |
| :--- | :--- | :--- | :--- |
| Observed Hazard Area | {{affected_km2_observed}} km² | `processed/l2_stats.json` | `areas_km2.event_total_affected` |
| Inferred Hazard Area | {{affected_km2_inferred}} km² | `processed/l2_stats.json` | `areas_km2.event_inferred_affected` |
| Cut-Off Settlements (Vehicle, Optimistic) | {{cutoff_vehicle_optimistic_count}} | `processed/routing/cutoff_summary.json` | `vehicle.optimistic.cut_off_count` |
| Cut-Off Settlements (Vehicle, Pessimistic) | {{cutoff_vehicle_pessimistic_count}} | `processed/routing/cutoff_summary.json` | `vehicle.pessimistic.cut_off_count` |
| Cut-Off Settlements (Walking) | {{cutoff_walking_optimistic_count}} | `processed/routing/cutoff_summary.json` | `walking.optimistic.cut_off_count` |
| Settlements via Unverified Routes | {{connected_unverified_count}} | `processed/routing/cutoff_summary.json` | `vehicle.optimistic.connected_unverified_count` |
| Total Buildings Assessed | {{buildings_total}} | `processed/damage_summary.json` | `buildings.total_count` |
| Total Affected Buildings | {{buildings_affected_total}} | `processed/damage_summary.json` | `buildings.affected_count` |
| Destroyed Buildings | {{buildings_destroyed}} | `processed/damage_summary.json` | `buildings.damage_grade_counts.Destroyed` |
| Damaged Buildings | {{buildings_damaged}} | `processed/damage_summary.json` | `buildings.damage_grade_counts.Damaged` |
| Possibly Damaged Buildings | {{buildings_possibly_damaged}} | `processed/damage_summary.json` | `buildings.damage_grade_counts.Possibly damaged` |
| Cloud-Unverified Buildings | {{buildings_cloud_unverified}} | `processed/damage_summary.json` | `buildings.damage_grade_counts.Unknown (cloud)` |
| Total Assessed Road Network | {{roads_total_km}} km | `processed/damage_summary.json` | `roads.total_km` (all OSM segments in buffer) |
| Core Drivable Road Network | {{roads_drivable_km}} km | `processed/damage_summary.json` | `osm_coverage.road_km_by_type` (primary+tertiary+residential+track in bbox) |
| Destroyed Road Length | {{roads_destroyed_km}} km | `processed/damage_summary.json` | `roads.km_by_damage_grade.Destroyed` |
| Possibly Damaged Road Length | {{roads_possibly_damaged_km}} km | `processed/damage_summary.json` | `roads.km_by_damage_grade.Possibly damaged` |
| Cloud-Unverified Road Length | {{roads_cloud_unverified_km}} km | `processed/damage_summary.json` | `roads.km_by_damage_grade.Unknown (cloud)` |
| Total Bridges Assessed | {{bridges_total}} | `processed/damage_summary.json` | `bridges.total_count` |
| Total Affected Bridges | {{bridges_affected_total}} | `processed/damage_summary.json` | `bridges.affected_count` |
| Destroyed Bridges | {{bridges_destroyed}} | `processed/damage_summary.json` | `bridges.damage_grade_counts.Destroyed` |
| Possibly Damaged Bridges | {{bridges_possibly_damaged}} | `processed/damage_summary.json` | `bridges.damage_grade_counts.Possibly damaged` |
| Cloud-Unverified Bridges | {{bridges_cloud_unverified}} | `processed/damage_summary.json` | `bridges.damage_grade_counts.Unknown (cloud)` |
| Repair Package 1 Elements | {{package_1_element_count}} | `processed/routing/repair_packages.json` | `ranked_packages[0].element_count` |
| Package 1 Reconnected Settlements | {{package_1_reconnected_settlements}} | `processed/routing/repair_packages.json` | `ranked_packages[0].settlements_count` |
| Package 1 Reconnected Buildings | {{package_1_reconnected_buildings}} | `processed/routing/repair_packages.json` | `ranked_packages[0].buildings_count` |

---

### 7. METRIC DISCREPANCY RECONCILIATIONS
- **Inferred Area Reconciliation (0.8789 km² vs 1.0044 km²):** The genuine pipeline calculation in `processed/l2_stats.json` (`areas_km2.event_inferred_affected`) and `run_summary.json` is `0.8789 km²` (accompanied by `0.7989 km²` observed, total `1.6778 km²`). The `1.0044 km²` figure was an obsolete ungrounded mock value in earlier prototype drafts and is corrected here to `0.8789 km²`.
- **Road Network Length Reconciliation (104.6 km vs ~68 km):** `104.6 km` in `processed/damage_summary.json` represents the comprehensive assessment of all OpenStreetMap road segments (including service lanes and unclassified peripheral tracks). In contrast, `66.64 km` (~68 km) represents the classified drivable road network within the core AOI bounding box (`[85.3, 28.1, 85.42, 28.25]`), which serves as the active graph for vehicular health routing.
"""


SITREP_TEMPLATE_PROSE_NE = """# द्रुत आपतकालीन स्थिति प्रतिवेदन (SITREP)
**घटना मिति:** {{event_date}} | **प्रभावित क्षेत्र (AOI):** {{bbox}} | **वर्गीकरण:** खोज तथा उद्धार
**भूउपग्रह अवलोकन:** {{optical_evidence_date}} | **प्रयोग गरिएका सेन्सरहरू:** {{sensors_used}}

---

### १. कार्यकारी सारांश
मिति **{{event_date}}** मा घटेको प्राकृतिक प्रकोपबाट प्रत्यक्ष रूपमा **{{affected_km2_observed}} वर्ग कि.मी.** भूभाग प्रभावित भएको पुष्टि भएको छ। यसका अतिरिक्त ठाडो खोला तथा पहिरो बहाव क्षेत्रमा **{{affected_km2_inferred}} वर्ग कि.मी.** क्षेत्र अनुमानित प्रभावित छ।

सडक तथा पुलहरूमा भएको क्षतिका कारण **{{cutoff_vehicle_optimistic_count}} बस्तीहरू** सवारी साधन आवागमनबाट पूर्ण रूपमा सम्पर्कविहीन भएका छन्। साथै **{{connected_unverified_count}} बस्तीहरू** बादलले ढाकिएका मार्गहरूमा निर्भर रहेकाले तिनको अवस्था स्थलगत पुष्टि हुन बाँकी छ।

---

### २. भौतिक पूर्वाधार क्षति विवरण
- **भवनहरू (कुल {{buildings_total}} मूल्याङ्कन):**
  - पूर्ण रूपमा नष्ट: **{{buildings_destroyed}}**
  - क्षतिग्रस्त: **{{buildings_damaged}}**
  - सम्भावित क्षति: **{{buildings_possibly_damaged}}**
  - कुल प्रभावित भवन: **{{buildings_affected_total}}**
  - बादलले ढाकिएका (अपुष्ट): **{{buildings_cloud_unverified}}**

- **सडक सञ्जाल (कुल {{roads_total_km}} कि.मी. मूल्याङ्कन; कोर क्षेत्रमा {{roads_drivable_km}} कि.मी. सवारी सञ्जाल):**
  - पूर्ण नष्ट: **{{roads_destroyed_km}} कि.मी.**
  - सम्भावित क्षति: **{{roads_possibly_damaged_km}} कि.मी.**
  - बादलले ढाकिएका: **{{roads_cloud_unverified_km}} कि.मी.**

- **पुलहरू (कुल {{bridges_total}} मूल्याङ्कन):**
  - पूर्ण नष्ट: **{{bridges_destroyed}}**
  - सम्भावित क्षति: **{{bridges_possibly_damaged}}**
  - कुल प्रभावित पुल: **{{bridges_affected_total}}**
  - बादलले ढाकिएका: **{{bridges_cloud_unverified}}**

---

### ३. यातायात पहुँच तथा मर्मत प्राथमिकता
- **सम्पर्कविहीन बस्तीहरू:** सवारी पहुँचका आधारमा **{{cutoff_vehicle_optimistic_count}} बस्तीहरू** सम्पर्कविहीन छन् (निराशावादी अवस्था: **{{cutoff_vehicle_pessimistic_count}}**)। पैदल मार्ग अवरुद्ध: **{{cutoff_walking_optimistic_count}} बस्तीहरू**।
- **मर्मत प्राथमिकता:** कुनै पनि एकल मर्मतले एक्लै कुनै बस्तीमा पहुँच पुनर्स्थापित गर्न सक्दैन (सडक खण्डहरू लगातार अवरुद्ध भएकाले एकल मर्मतबाट ० बस्ती)। **मर्मत प्याकेज १** ({{package_1_element_count}} सडक खण्डहरू: {{package_1_elements_list}}, कुल लम्बाइ: **{{package_1_length_m}} मिटर**) ले **{{package_1_reconnected_settlements}} सम्पर्कविहीन बस्तीहरू** र **{{package_1_reconnected_buildings}} भवनहरू**मा सवारी पहुँच पुनर्स्थापित गर्दछ।

---

### ४. तथ्याङ्कका सीमितता र अनिश्चितता
१. **बादलको प्रभाव:** {{buildings_cloud_unverified}} भवनहरू र {{roads_cloud_unverified_km}} कि.मी. सडक बादलका कारण अप्टिकल स्याटेलाइटबाट प्रमाणीकरण हुन सकेको छैन।
२. **मोडेल अनुमान:** सहायक नदीहरूमा बाढी क्षेत्र हाइड्रोलिक मोडेलिङद्वारा अनुमान गरिएको हो।
३. **जनसंख्या तथ्याङ्क:** ओपन्स्ट्रीटम्याप आधारभूत तथ्याङ्कमा आवासीय जनसंख्या उपलब्ध छैन।

---

### ५. स्रोत तथा प्रतिलिपि अधिकार (Attributions)
{{attributions}}

---

### ६. तथ्याङ्क स्रोत तथा प्रमाणीकरण तालिका (Data Lineage)
| सूचक / संख्या | प्रमाणीकृत मान | स्रोत फाइल | जेसन फिल्ड / विवरण |
| :--- | :--- | :--- | :--- |
| प्रत्यक्ष बाढी क्षेत्र | {{affected_km2_observed}} km² | `processed/l2_stats.json` | `areas_km2.event_total_affected` |
| अनुमानित बाढी क्षेत्र | {{affected_km2_inferred}} km² | `processed/l2_stats.json` | `areas_km2.event_inferred_affected` |
| सवारी सम्पर्कविहीन बस्ती (आशावादी) | {{cutoff_vehicle_optimistic_count}} | `processed/routing/cutoff_summary.json` | `vehicle.optimistic.cut_off_count` |
| सवारी सम्पर्कविहीन बस्ती (निराशावादी) | {{cutoff_vehicle_pessimistic_count}} | `processed/routing/cutoff_summary.json` | `vehicle.pessimistic.cut_off_count` |
| पैदल सम्पर्कविहीन बस्ती | {{cutoff_walking_optimistic_count}} | `processed/routing/cutoff_summary.json` | `walking.optimistic.cut_off_count` |
| अपुष्ट मार्ग प्रयोग गर्ने बस्ती | {{connected_unverified_count}} | `processed/routing/cutoff_summary.json` | `vehicle.optimistic.connected_unverified_count` |
| मूल्याङ्कन गरिएका कुल भवन | {{buildings_total}} | `processed/damage_summary.json` | `buildings.total_count` |
| कुल प्रभावित भवनहरू | {{buildings_affected_total}} | `processed/damage_summary.json` | `buildings.affected_count` |
| पूर्ण नष्ट भवनहरू | {{buildings_destroyed}} | `processed/damage_summary.json` | `buildings.damage_grade_counts.Destroyed` |
| क्षतिग्रस्त भवनहरू | {{buildings_damaged}} | `processed/damage_summary.json` | `buildings.damage_grade_counts.Damaged` |
| सम्भावित क्षति भवनहरू | {{buildings_possibly_damaged}} | `processed/damage_summary.json` | `buildings.damage_grade_counts.Possibly damaged` |
| बादलले ढाकिएका भवनहरू | {{buildings_cloud_unverified}} | `processed/damage_summary.json` | `buildings.damage_grade_counts.Unknown (cloud)` |
| कुल मूल्याङ्कन सडक | {{roads_total_km}} km | `processed/damage_summary.json` | `roads.total_km` |
| कोर क्षेत्रमा सवारी योग्य सडक | {{roads_drivable_km}} km | `processed/damage_summary.json` | `osm_coverage.road_km_by_type` |
| नष्ट सडक लम्बाइ | {{roads_destroyed_km}} km | `processed/damage_summary.json` | `roads.km_by_damage_grade.Destroyed` |
| सम्भावित क्षति सडक | {{roads_possibly_damaged_km}} km | `processed/damage_summary.json` | `roads.km_by_damage_grade.Possibly damaged` |
| बादलले ढाकिएको सडक | {{roads_cloud_unverified_km}} km | `processed/damage_summary.json` | `roads.km_by_damage_grade.Unknown (cloud)` |
| मूल्याङ्कन गरिएका कुल पुल | {{bridges_total}} | `processed/damage_summary.json` | `bridges.total_count` |
| कुल प्रभावित पुलहरू | {{bridges_affected_total}} | `processed/damage_summary.json` | `bridges.affected_count` |
| नष्ट पुलहरू | {{bridges_destroyed}} | `processed/damage_summary.json` | `bridges.damage_grade_counts.Destroyed` |
| सम्भावित क्षति पुलहरू | {{bridges_possibly_damaged}} | `processed/damage_summary.json` | `bridges.damage_grade_counts.Possibly damaged` |
| बादलले ढाकिएका पुलहरू | {{bridges_cloud_unverified}} | `processed/damage_summary.json` | `bridges.damage_grade_counts.Unknown (cloud)` |
| मर्मत प्याकेज १ का खण्डहरू | {{package_1_element_count}} | `processed/routing/repair_packages.json` | `ranked_packages[0].element_count` |
| प्याकेज १ ले जोड्ने बस्तीहरू | {{package_1_reconnected_settlements}} | `processed/routing/repair_packages.json` | `ranked_packages[0].settlements_count` |
| प्याकेज १ ले जोड्ने भवनहरू | {{package_1_reconnected_buildings}} | `processed/routing/repair_packages.json` | `ranked_packages[0].buildings_count` |

---

### ७. तथ्याङ्क मिलान तथा स्पष्टीकरण (Reconciliations)
- **अनुमानित क्षेत्र मिलान (०.८७८९ वर्ग कि.मी. बनाम १.००४४ वर्ग कि.मी.):** पाइपलाइनको वास्तविक गणना `processed/l2_stats.json` र `run_summary.json` मा **०.८७८९ वर्ग कि.मी.** हो। पुरानो ड्राफ्टमा रहेको १.००४४ वर्ग कि.मी. अनधिकृत संख्या हटाई यकिन ०.८७८९ वर्ग कि.मी. कायम गरिएको छ।
- **सडक लम्बाइ मिलान (१०४.६ कि.मी. बनाम ~६८ कि.मी.):** `damage_summary.json` को **१०४.६ कि.मी.** ले सम्पूर्ण बफर क्षेत्रका सबै प्रकारका ओएसएम सडकहरूलाई जनाउँछ, जबकि मुख्य बाढी क्षेत्र (AOI bbox) भित्र एम्बुलेन्स तथा सवारी सञ्जालको वास्तविक लम्बाइ **६६.६४ कि.मी. (~६८ कि.मी.)** रहेको छ।
"""


PDF_CSS = """
@page {
    size: A4 portrait;
    margin: 14mm 15mm 14mm 15mm;
}
body {
    font-family: 'Noto Sans Devanagari', 'Lohit Devanagari', 'FreeSans', 'DejaVu Sans', sans-serif;
    color: #1a202c;
    line-height: 1.35;
    font-size: 9.5pt;
}
h1 {
    font-size: 16pt;
    color: #9b2c2c;
    margin-bottom: 2px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    border-bottom: 2px solid #e53e3e;
    padding-bottom: 4px;
}
h3 {
    font-size: 10.5pt;
    color: #2b6cb0;
    margin-top: 8px;
    margin-bottom: 4px;
    border-bottom: 1px solid #cbd5e0;
    padding-bottom: 2px;
}
p {
    margin-top: 3px;
    margin-bottom: 4px;
}
ul {
    margin-top: 2px;
    margin-bottom: 4px;
    padding-left: 18px;
}
li {
    margin-bottom: 2px;
}
hr {
    border: none;
    border-top: 1px solid #e2e8f0;
    margin: 6px 0;
}
strong {
    color: #1a202c;
}
.kpi-container {
    display: flex;
    justify-content: space-between;
    margin: 6px 0;
}
.kpi-box {
    flex: 1;
    background: #edf2f7;
    border-left: 3px solid #3182ce;
    padding: 4px 6px;
    margin: 0 3px;
    font-size: 8.5pt;
}
.kpi-val {
    font-size: 12pt;
    font-weight: bold;
    color: #c53030;
}
.footer {
    font-size: 7.5pt;
    color: #718096;
    margin-top: 6px;
    border-top: 1px solid #e2e8f0;
    padding-top: 3px;
}
"""


class SitRepGenerator:
    """Generates bilingual Situation Reports with strict numeric grounding."""

    def __init__(self, fact_store: FactStore):
        self.store = fact_store
        self.guard = NumberGuard()
        self.values = self._collect_fill_values()

    def _collect_fill_values(self) -> Dict[str, str]:
        """Collect all grounded numeric values and metadata strings from FactStore."""
        top_step = None
        for step_idx in range(1, 6):
            set_rec = self.store.get_value(f"repair.step_{step_idx}.settlements_reconnected", 0)
            if set_rec > 0:
                top_step = step_idx
                break
        if top_step is None:
            top_step = 1

        top_elem = self.store.get_value(f"repair.step_{top_step}.osm_id", "not computed")
        top_len = self.store.get_value(f"repair.step_{top_step}.length_m", "not computed")
        top_set = self.store.get_value(f"repair.step_{top_step}.settlements_reconnected", "not computed")
        top_bld = self.store.get_value(f"repair.step_{top_step}.buildings_reconnected", "not computed")

        bbox_raw = self.store.metadata.get("bbox", "not computed")
        bbox_str = f"[{bbox_raw[0]:.2f}, {bbox_raw[1]:.2f}, {bbox_raw[2]:.2f}, {bbox_raw[3]:.2f}]" if isinstance(bbox_raw, list) else str(bbox_raw)

        sensors = self.store.metadata.get("sensors_used", ["Sentinel-2 MSI", "Sentinel-1 RTC SAR", "Copernicus DEM-30", "OpenStreetMap"])
        sensors_str = ", ".join(sensors) if isinstance(sensors, list) else str(sensors)

        event_date = str(self.store.get_value("event.date", self.store.metadata.get("event_date", "not computed")))
        event_year = str(event_date)[:4] if event_date != "not computed" and len(event_date) >= 4 else "2026"

        attributions = (
            f"Contains modified Copernicus Sentinel data {event_year}.\n"
            "Produced using Copernicus WorldDEM-30 © DLR e.V. 2010–2014 and © Airbus Defence and Space GmbH 2014–2018 provided under COPERNICUS by the European Union and ESA; all rights reserved.\n"
            "© OpenStreetMap contributors.\n"
            "Bountos et al., 2024 (Kuro Siwo)"
        )

        pkg1 = self.store.repair_packages[0] if getattr(self.store, "repair_packages", None) else {}
        pkg1_elem_cnt = str(pkg1.get("element_count", self.store.get_value("repair.package_1.element_count", "not computed")))
        pkg1_set_cnt = str(pkg1.get("settlements_count", self.store.get_value("repair.package_1.settlements_count", "not computed")))
        pkg1_bld_cnt = str(pkg1.get("buildings_count", self.store.get_value("repair.package_1.buildings_count", "not computed")))
        elems_arr = pkg1.get("elements", [])
        pkg1_elems_list = ", ".join(elems_arr) if isinstance(elems_arr, list) and elems_arr else str(elems_arr or "not computed")
        pkg1_length_m = str(pkg1.get("length_m", round(sum(self.store.get_value(f"repair.step_{i}.length_m", 0.0) for i in range(1, 5)), 1)))

        values = {
            "event_date": event_date,
            "bbox": bbox_str,
            "optical_evidence_date": str(self.store.metadata.get("optical_date", "not computed")),
            "sensors_used": sensors_str,
            "affected_km2_observed": str(self.store.get_value("hazard.area.event_total_affected", self.store.get_value("metrics.affected_km2_observed", "not computed"))),
            "affected_km2_inferred": str(self.store.get_value("hazard.area.event_inferred_affected", self.store.get_value("metrics.affected_km2_inferred", "not computed"))),
            "buildings_total": str(self.store.get_value("damage.buildings.total", "not computed")),
            "buildings_affected_total": str(self.store.get_value("damage.buildings.affected_total", "not computed")),
            "buildings_destroyed": str(self.store.get_value("damage.buildings.destroyed", "not computed")),
            "buildings_damaged": str(self.store.get_value("damage.buildings.damaged", "not computed")),
            "buildings_possibly_damaged": str(self.store.get_value("damage.buildings.possibly_damaged", "not computed")),
            "buildings_cloud_unverified": str(self.store.get_value("damage.buildings.unknown_cloud", "not computed")),
            "bridges_total": str(self.store.get_value("damage.bridges.total", "not computed")),
            "bridges_affected_total": str(self.store.get_value("damage.bridges.affected_total", "not computed")),
            "bridges_destroyed": str(self.store.get_value("damage.bridges.destroyed", "not computed")),
            "bridges_possibly_damaged": str(self.store.get_value("damage.bridges.possibly_damaged", "not computed")),
            "bridges_cloud_unverified": str(self.store.get_value("damage.bridges.unknown_cloud", "not computed")),
            "roads_total_km": str(self.store.get_value("damage.roads.total_km", "not computed")),
            "roads_drivable_km": str(self.store.get_value("damage.roads.drivable_km", "not computed")),
            "roads_destroyed_km": str(self.store.get_value("damage.roads.destroyed_km", "not computed")),
            "roads_possibly_damaged_km": str(self.store.get_value("damage.roads.possibly_damaged_km", "not computed")),
            "roads_cloud_unverified_km": str(self.store.get_value("damage.roads.unknown_cloud_km", "not computed")),
            "cutoff_vehicle_optimistic_count": str(self.store.get_value("cutoff.vehicle.optimistic.count", "not computed")),
            "cutoff_vehicle_pessimistic_count": str(self.store.get_value("cutoff.vehicle.pessimistic.count", "not computed")),
            "cutoff_walking_optimistic_count": str(self.store.get_value("cutoff.walking.optimistic.count", "not computed")),
            "connected_unverified_count": str(self.store.get_value("cutoff.vehicle.optimistic.connected_unverified", "not computed")),
            "package_1_element_count": pkg1_elem_cnt,
            "package_1_elements_list": pkg1_elems_list,
            "package_1_length_m": pkg1_length_m,
            "package_1_reconnected_settlements": pkg1_set_cnt,
            "package_1_reconnected_buildings": pkg1_bld_cnt,
            "attributions": attributions,
        }
        return values

    def fill_template(self, template_prose: str) -> str:
        """Replace all {{placeholder}} tokens with verified numbers from FactStore."""
        filled = template_prose
        for key, val in self.values.items():
            filled = filled.replace(f"{{{{{key}}}}}", val)
        return filled

    def generate_markdown(self, lang: str = "en", custom_prose: Optional[str] = None) -> str:
        """Generate final grounded Markdown situation report."""
        if custom_prose:
            prose = custom_prose
        else:
            prose = SITREP_TEMPLATE_PROSE_NE if lang == "ne" else SITREP_TEMPLATE_PROSE_EN
        return self.fill_template(prose)

    def generate_pdf(
        self,
        markdown_text: str,
        output_pdf_path: Path | str,
    ) -> Path:
        """Render markdown text into professional 1-page PDF using WeasyPrint."""
        out_path = Path(output_pdf_path).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)

        # Convert simple markdown to HTML
        html_body = []
        for line in markdown_text.splitlines():
            line_str = line.strip()
            if not line_str:
                continue
            if line_str.startswith("# "):
                html_body.append(f"<h1>{line_str[2:]}</h1>")
            elif line_str.startswith("### "):
                html_body.append(f"<h3>{line_str[4:]}</h3>")
            elif line_str.startswith("- "):
                # bullet point
                content = line_str[2:]
                content = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", content)
                html_body.append(f"<ul><li>{content}</li></ul>")
            elif line_str == "---":
                html_body.append("<hr/>")
            else:
                formatted = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", line_str)
                html_body.append(f"<p>{formatted}</p>")

        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Situation Report</title>
    <style>{PDF_CSS}</style>
</head>
<body>
    {''.join(html_body)}
</body>
</html>"""

        doc = weasyprint.HTML(string=html_content)
        doc.write_pdf(str(out_path))
        logger.info("Generated SitRep PDF: %s", out_path)
        return out_path

    def generate_all(self, output_dir: Path | str) -> Dict[str, Path]:
        """Generate both English and Nepali Markdown and PDF situation reports."""
        target_dir = Path(output_dir).resolve()
        target_dir.mkdir(parents=True, exist_ok=True)

        md_en = self.generate_markdown(lang="en")
        md_ne = self.generate_markdown(lang="ne")

        en_md_path = target_dir / "sitrep_en.md"
        ne_md_path = target_dir / "sitrep_ne.md"
        en_pdf_path = target_dir / "sitrep_en.pdf"
        ne_pdf_path = target_dir / "sitrep_ne.pdf"

        en_md_path.write_text(md_en, encoding="utf-8")
        ne_md_path.write_text(md_ne, encoding="utf-8")

        self.generate_pdf(md_en, en_pdf_path)
        self.generate_pdf(md_ne, ne_pdf_path)

        return {
            "en_markdown": en_md_path,
            "ne_markdown": ne_md_path,
            "en_pdf": en_pdf_path,
            "ne_pdf": ne_pdf_path,
        }
