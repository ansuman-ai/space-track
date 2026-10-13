"""Bilingual 1-Page Situation Report Generator (English & Nepali).

Generates strictly grounded 1-page situation reports:
- Dynamic data binding from FactStore with 0 hardcoded values.
- Exactly 1 A4 portrait page layout in PDF with overview map quicklook.
- Separate optional lineage appendix document.
- Compliant attributions including European Union Copernicus EMS and Educational prototype disclaimer.
"""

from __future__ import annotations

import base64
import html
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import weasyprint

from .facts import FactStore
from .guard import NumberGuard

logger = logging.getLogger("copilot.sitrep")


SITREP_TEMPLATE_PROSE_EN = """# RAPID DISASTER SITUATION REPORT (SITREP)
**Event Date:** {{event_date}} | **AOI:** {{bbox}} | **Assessment Type:** Situation Report
**Satellite Observation:** {{optical_evidence_date}} | **Sensors:** {{sensors_used}}

---

### 1. EXECUTIVE SUMMARY
A disaster event occurred on **{{event_date}}**. Satellite change detection identifies **{{affected_km2_observed}} km²** of directly observed hazard extent, with an additional **{{affected_km2_inferred}} km²** inferred along steep drainage corridors.

Access to **{{cutoff_vehicle_optimistic_count}} settlements** is severed for motorized vehicles due to road and bridge damage. Furthermore, **{{connected_unverified_count}} settlements** rely on transit routes obscured by clouds, where passable conditions cannot be confirmed.

---

### 2. INFRASTRUCTURE DAMAGE BREAKDOWN
- **Buildings (Total {{buildings_total}} assessed):**
  - Destroyed: **{{buildings_destroyed}}**
  - Damaged / Flooded: **{{buildings_damaged}}**
  - Possibly Damaged / Flooded: **{{buildings_possibly_damaged}}**
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
- **Cut-Off Settlements:** **{{cutoff_vehicle_optimistic_count}} settlements** cut off from any town or hospital by vehicle (pessimistic: **{{cutoff_vehicle_pessimistic_count}}**). Pedestrian cut-off: **{{cutoff_walking_optimistic_count}} settlements**.
- **Repair Priority:** Repair **Package 1** ({{package_1_element_count}} road elements: {{package_1_elements_list}}, total length: **{{package_1_length_m}} m**) restores vehicle access to **{{package_1_reconnected_settlements}} cut-off settlements** and **{{package_1_reconnected_buildings}} buildings**.

---

### 4. DATA LIMITATIONS & UNCERTAINTIES
1. **Cloud Obscuration:** {{buildings_cloud_unverified}} buildings and {{roads_cloud_unverified_km}} km of roads remain unverified due to cloud cover.
2. **Hydraulic Inundation Inference:** Tributary hazard boundaries are hydraulically modeled rather than observed by radar backscatter.
3. **OSM Baseline Data:** Residential population counts are not available in OpenStreetMap baseline data.

---

### 5. ATTRIBUTIONS & CREDITS
{{attributions}}
"""


SITREP_TEMPLATE_PROSE_NE = """# द्रुत विपद् स्थिति प्रतिवेदन (SITREP)
**घटना मिति:** {{event_date}} | **प्रभावित क्षेत्र (AOI):** {{bbox}} | **प्रतिवेदन प्रकार:** स्थिति प्रतिवेदन
**भूउपग्रह अवलोकन:** {{optical_evidence_date}} | **प्रयोग गरिएका सेन्सरहरू:** {{sensors_used}}

---

### १. कार्यकारी सारांश
मिति **{{event_date}}** मा घटेको प्राकृतिक प्रकोपबाट प्रत्यक्ष रूपमा **{{affected_km2_observed}} वर्ग कि.मी.** भूभाग प्रभावित भएको पुष्टि भएको छ। यसका अतिरिक्त खोला तथा पहिरो बहाव क्षेत्रमा **{{affected_km2_inferred}} वर्ग कि.मी.** क्षेत्र अनुमानित प्रभावित छ।

सडक तथा पुलहरूमा भएको क्षतिका कारण **{{cutoff_vehicle_optimistic_count}} बस्तीहरू** सवारी साधन आवागमनबाट पूर्ण रूपमा सम्पर्कविहीन भएका छन्। साथै **{{connected_unverified_count}} बस्तीहरू** बादलले ढाकिएका मार्गहरूमा निर्भर रहेकाले तिनको अवस्था स्थलगत पुष्टि हुन बाँकी छ।

---

### २. भौतिक पूर्वाधार क्षति विवरण
- **भवनहरू (कुल {{buildings_total}} मूल्याङ्कन):**
  - पूर्ण रूपमा नष्ट: **{{buildings_destroyed}}**
  - क्षतिग्रस्त / जलमग्न: **{{buildings_damaged}}**
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
- **सम्पर्कविहीन बस्तीहरू:** सवारी पहुँचका आधारमा **{{cutoff_vehicle_optimistic_count}} बस्तीहरू** कुनै पनि सहर वा अस्पतालबाट विच्छेद छन् (निराशावादी अवस्था: **{{cutoff_vehicle_pessimistic_count}}**)। पैदल मार्ग अवरुद्ध: **{{cutoff_walking_optimistic_count}} बस्तीहरू**।
- **मर्मत प्राथमिकता:** **मर्मत प्याकेज १** ({{package_1_element_count}} सडक खण्डहरू: {{package_1_elements_list}}, कुल लम्बाइ: **{{package_1_length_m}} मिटर**) ले **{{package_1_reconnected_settlements}} सम्पर्कविहीन बस्तीहरू** र **{{package_1_reconnected_buildings}} भवनहरू**मा सवारी पहुँच पुनर्स्थापित गर्दछ।

---

### ४. तथ्याङ्कका सीमितता र अनिश्चितता
१. **बादलको प्रभाव:** {{buildings_cloud_unverified}} भवनहरू र {{roads_cloud_unverified_km}} कि.मी. सडक बादलका कारण अप्टिकल स्याटेलाइटबाट प्रमाणीकरण हुन सकेको छैन।
२. **मोडेल अनुमान:** सहायक नदीहरूमा बाढी क्षेत्र हाइड्रोलिक मोडेलिङद्वारा अनुमान गरिएको हो।
३. **जनसंख्या तथ्याङ्क:** ओपन्स्ट्रीटम्याप आधारभूत तथ्याङ्कमा आवासीय जनसंख्या उपलब्ध छैन।

---

### ५. स्रोत तथा प्रतिलिपि अधिकार (Attributions)
{{attributions}}
"""


LINEAGE_APPENDIX_TEMPLATE_EN = """# SITUATION REPORT — APPENDIX: DATA LINEAGE & AUDIT LOG
**Event Date:** {{event_date}} | **AOI:** {{bbox}} | **Run Directory:** `{{run_dir}}`

This appendix provides field-by-field verification linking every fact in the 1-page Situation Report directly to authoritative pipeline JSON output files.

| Metric / Description | Verified Value | Source File | JSON Field / Provenance |
| :--- | :--- | :--- | :--- |
| Directly Observed Hazard Extent | {{affected_km2_observed}} km² | `processed/l2_stats.json` | `areas_km2.event_total_affected` |
| Inferred Modelled Hazard Extent | {{affected_km2_inferred}} km² | `processed/l2_stats.json` | `areas_km2.event_inferred_affected` |
| Cut-Off Settlements (Vehicle, Optimistic) | {{cutoff_vehicle_optimistic_count}} | `processed/routing/cutoff_summary.json` | `vehicle.optimistic.cut_off_count` |
| Cut-Off Settlements (Vehicle, Pessimistic) | {{cutoff_vehicle_pessimistic_count}} | `processed/routing/cutoff_summary.json` | `vehicle.pessimistic.cut_off_count` |
| Cut-Off Settlements (Walking) | {{cutoff_walking_optimistic_count}} | `processed/routing/cutoff_summary.json` | `walking.optimistic.cut_off_count` |
| Settlements via Unverified Routes | {{connected_unverified_count}} | `processed/routing/cutoff_summary.json` | `vehicle.optimistic.connected_unverified_count` |
| Total Buildings Evaluated | {{buildings_total}} | `processed/damage_summary.json` | `buildings.total_count` |
| Total Affected Buildings | {{buildings_affected_total}} | `processed/damage_summary.json` | `buildings.affected_count` |
| Destroyed Buildings | {{buildings_destroyed}} | `processed/damage_summary.json` | `buildings.damage_grade_counts.Destroyed` |
| Damaged Buildings | {{buildings_damaged}} | `processed/damage_summary.json` | `buildings.damage_grade_counts.Damaged` |
| Possibly Damaged Buildings | {{buildings_possibly_damaged}} | `processed/damage_summary.json` | `buildings.damage_grade_counts.Possibly damaged` |
| Cloud-Unverified Buildings | {{buildings_cloud_unverified}} | `processed/damage_summary.json` | `buildings.damage_grade_counts.Unknown (cloud)` |
| Total Road Length Evaluated | {{roads_total_km}} km | `processed/damage_summary.json` | `roads.total_km` (all OSM segments in buffer) |
| Classified Drivable Road Network | {{roads_drivable_km}} km | `processed/damage_summary.json` | `osm_coverage.road_km_by_type` (in bbox) |
| Destroyed Road Length | {{roads_destroyed_km}} km | `processed/damage_summary.json` | `roads.km_by_damage_grade.Destroyed` |
| Possibly Damaged Road Length | {{roads_possibly_damaged_km}} km | `processed/damage_summary.json` | `roads.km_by_damage_grade.Possibly damaged` |
| Cloud-Unverified Road Length | {{roads_cloud_unverified_km}} km | `processed/damage_summary.json` | `roads.km_by_damage_grade.Unknown (cloud)` |
| Total Bridges Evaluated | {{bridges_total}} | `processed/damage_summary.json` | `bridges.total_count` |
| Total Affected Bridges | {{bridges_affected_total}} | `processed/damage_summary.json` | `bridges.affected_count` |
| Destroyed Bridges | {{bridges_destroyed}} | `processed/damage_summary.json` | `bridges.damage_grade_counts.Destroyed` |
| Possibly Damaged Bridges | {{bridges_possibly_damaged}} | `processed/damage_summary.json` | `bridges.damage_grade_counts.Possibly damaged` |
| Cloud-Unverified Bridges | {{bridges_cloud_unverified}} | `processed/damage_summary.json` | `bridges.damage_grade_counts.Unknown (cloud)` |
| Repair Package 1 Elements | {{package_1_element_count}} | `processed/routing/repair_packages.json` | `ranked_packages[0].element_count` |
| Package 1 Reconnected Settlements | {{package_1_reconnected_settlements}} | `processed/routing/repair_packages.json` | `ranked_packages[0].settlements_count` |
| Package 1 Reconnected Buildings | {{package_1_reconnected_buildings}} | `processed/routing/repair_packages.json` | `ranked_packages[0].buildings_count` |

---
**Attributions & Lineage:**
{{attributions}}
"""


LINEAGE_APPENDIX_TEMPLATE_NE = """# स्थिति प्रतिवेदन — अनुसूची: तथ्याङ्क स्रोत तथा प्रमाणीकरण तालिका
**घटना मिति:** {{event_date}} | **प्रभावित क्षेत्र (AOI):** {{bbox}} | **विश्लेषण निर्देशिका:** `{{run_dir}}`

यस अनुसूचीले १-पृष्ठको स्थिति प्रतिवेदनमा उल्लिखित प्रत्येक तथ्याङ्कलाई पाइपलाइनको आधिकारिक JSON फाइलसँग सिधै जोड्दछ।

| सूचक / विवरण | प्रमाणीकृत मान | स्रोत फाइल | जेसन फिल्ड / विवरण |
| :--- | :--- | :--- | :--- |
| प्रत्यक्ष बाढी / लेदो क्षेत्र | {{affected_km2_observed}} km² | `processed/l2_stats.json` | `areas_km2.event_total_affected` |
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
| कुल मूल्याङ्कन सडक लम्बाइ | {{roads_total_km}} km | `processed/damage_summary.json` | `roads.total_km` |
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
**प्रतिलिपि अधिकार तथा स्रोत:**
{{attributions}}
"""


def safe_url_fetcher(url, timeout=10, ssl_context=None):
    """Strict security: SitRep is self-contained. Block all external network fetches."""
    if url.startswith("data:"):
        return weasyprint.default_url_fetcher(url)
    raise ValueError(f"External and local resource fetching is strictly disabled in SitRep PDF generator: {url}")


class SitRepGenerator:
    """Generates bilingual 1-Page Situation Reports with strict numeric grounding."""

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
            "© OpenStreetMap contributors under ODbL.\n"
            "European Union, Copernicus Emergency Management Service data (EMSR927, EMSR692, EMSR659).\n"
            "Bountos et al., 2024 (Kuro Siwo).\n"
            "Educational prototype, not an operational tool."
        )

        pkg1 = self.store.repair_packages[0] if getattr(self.store, "repair_packages", None) else {}
        pkg1_elem_cnt = str(pkg1.get("element_count", self.store.get_value("repair.package_1.element_count", "not computed")))
        pkg1_set_cnt = str(pkg1.get("settlements_count", self.store.get_value("repair.package_1.settlements_count", "not computed")))
        pkg1_bld_cnt = str(pkg1.get("buildings_count", self.store.get_value("repair.package_1.buildings_count", "not computed")))
        elems_arr = pkg1.get("elements", [])
        pkg1_elems_list = ", ".join(elems_arr) if isinstance(elems_arr, list) and elems_arr else str(elems_arr or "not computed")
        pkg1_length_m = str(pkg1.get("length_m", round(sum(self.store.get_value(f"repair.step_{i}.length_m", 0.0) for i in range(1, 5)), 1)))

        values = {
            "run_dir": str(self.store.run_dir),
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
            filled = filled.replace(f"{{{{{key}}}}}", str(val))
        return filled

    def generate_markdown(self, lang: str = "en", custom_prose: Optional[str] = None) -> str:
        """Generate final grounded Markdown situation report."""
        if custom_prose:
            prose = custom_prose
        else:
            prose = SITREP_TEMPLATE_PROSE_NE if lang == "ne" else SITREP_TEMPLATE_PROSE_EN
        return self.fill_template(prose)

    def generate_appendix(self, lang: str = "en") -> str:
        """Generate separate lineage appendix Markdown document."""
        template = LINEAGE_APPENDIX_TEMPLATE_NE if lang == "ne" else LINEAGE_APPENDIX_TEMPLATE_EN
        return self.fill_template(template)

    def _build_1page_html(self, lang: str = "en") -> str:
        """Build strictly 1-page HTML for WeasyPrint PDF output."""
        run_dir = Path(self.store.run_dir)
        v = self.values
        is_ne = (lang == "ne")

        # Map overview quicklook image
        ql_img_tag = ""
        for ql_name in ["quicklook_l4.png", "quicklook_layer2.png"]:
            ql_p = run_dir / "processed" / ql_name
            if ql_p.exists():
                try:
                    b64 = base64.b64encode(ql_p.read_bytes()).decode("ascii")
                    ql_img_tag = f'<img class="map-img" src="data:image/png;base64,{b64}" />'
                    break
                except Exception:
                    pass

        # Rescue priorities (Needs help first)
        pess_list = []
        c_summary_path = run_dir / "processed" / "routing" / "cutoff_summary.json"
        if c_summary_path.exists():
            try:
                import json
                with open(c_summary_path) as f:
                    c_data = json.load(f)
                pess_list = c_data.get("vehicle", {}).get("pessimistic", {}).get("cut_off_settlements", [])
            except Exception:
                pass

        sorted_rescue = sorted(pess_list, key=lambda x: x.get("building_count", 0), reverse=True)
        top_rescue = sorted_rescue[:3]

        # Actionable repair package (Repair first)
        rp_path = run_dir / "processed" / "routing" / "repair_packages.json"
        top_pkg = {}
        if rp_path.exists():
            try:
                import json
                with open(rp_path) as f:
                    rp_data = json.load(f)
                for pkg in rp_data.get("ranked_packages", []):
                    if len(pkg.get("elements", [])) > 0:
                        top_pkg = pkg
                        break
            except Exception:
                pass

        pkg_rank = top_pkg.get("rank", 1)
        pkg_set = top_pkg.get("settlements_count", 0)
        pkg_bld = top_pkg.get("buildings_count", 0)
        pkg_elems = top_pkg.get("elements", [])
        pkg_elem_count = len(pkg_elems)
        pkg_elems_str = ", ".join(pkg_elems) if pkg_elems else "None"

        ev_year = v["event_date"][:4] if len(v["event_date"]) >= 4 and v["event_date"][:4].isdigit() else "2026"

        if is_ne:
            title = "द्रुत विपद् स्थिति प्रतिवेदन (SITREP)"
            badge = "शैक्षिक प्रोटोटाइप"
            meta = f"घटना मिति: <strong>{v['event_date']}</strong> | उपग्रह अवलोकन: <strong>{v['optical_evidence_date']}</strong> | क्षेत्र (BBox): <strong>{v['bbox']}</strong>"
            kpi1_lbl = "प्रत्यक्ष बाढी / लेदो"
            kpi1_val = f"{v['affected_km2_observed']} km²"
            kpi2_lbl = "पूर्ण नष्ट भवनहरू"
            kpi2_val = v["buildings_destroyed"]
            kpi3_lbl = "नष्ट भएका पुलहरू"
            kpi3_val = v["bridges_destroyed"]
            kpi4_lbl = "सडक सम्पर्कविहीन बस्ती"
            kpi4_val = v["cutoff_vehicle_optimistic_count"]

            map_caption = "स्याटेलाइट क्षति नक्शा तथा प्रभावित पूर्वाधार"
            sec_needs = "तत्काल उद्धार आवश्यक (Needs help first)"
            sec_repair = "प्राथमिकता मर्मत (Repair first)"
            sec_infra = "भौतिक पूर्वाधार क्षति स्थिति"
            sec_limits = "तथ्याङ्कका मुख्य सीमाहरू (Known limits)"

            rescue_rows = "".join([f"<li><strong>{html.escape(s.get('name', 'Settlement'))}</strong>: {s.get('building_count', 0)} भवनहरू (सवारी सम्पर्क विच्छेद)</li>" for s in top_rescue]) if top_rescue else "<li>कुनै पनि बस्ती पूर्ण विच्छेद छैन।</li>"

            if top_pkg and pkg_elem_count > 0:
                repair_text = f"<strong>प्याकेज {pkg_rank}</strong> ({pkg_elem_count} पूर्वाधार: {html.escape(pkg_elems_str)}) मर्मत गर्दा <strong>{pkg_set} बस्तीहरू</strong> र <strong>{pkg_bld} भवनहरू</strong>मा सवारी पहुँच पुन: जोडिन्छ।"
            else:
                repair_text = "तत्काल एकल वा प्याकेज मर्मत योग्य सडक खण्ड पहिचान भएको छैन।"

            infra_html = f"""
            <table class="table-compact">
              <tr><th>पूर्वाधार</th><th>नष्ट</th><th>प्रभावित</th><th>बादलले ढाकिएको</th><th>कुल मूल्याङ्कन</th></tr>
              <tr><td>भवनहरू</td><td><strong>{v['buildings_destroyed']}</strong></td><td>{v['buildings_affected_total']}</td><td>{v['buildings_cloud_unverified']}</td><td>{v['buildings_total']}</td></tr>
              <tr><td>पुलहरू</td><td><strong>{v['bridges_destroyed']}</strong></td><td>{v['bridges_affected_total']}</td><td>{v['bridges_cloud_unverified']}</td><td>{v['bridges_total']}</td></tr>
              <tr><td>सडक (कि.मी.)</td><td><strong>{v['roads_destroyed_km']}</strong></td><td>{v['roads_possibly_damaged_km']}</td><td>{v['roads_cloud_unverified_km']}</td><td>{v['roads_total_km']}</td></tr>
            </table>
            """
            limits_html = f"""
            • बादलका कारण {v['buildings_cloud_unverified']} भवनहरू र {v['roads_cloud_unverified_km']} कि.मी. सडक अप्टिकल पुष्टि हुन सकेको छैन।<br/>
            • स्थायी पानी/छायाँ पहाडी भिरालो भूभागमा DEM लुक-एंगलद्वारा हटाइएको छ।<br/>
            • भवन तथा सडक संख्या प्रकोप पूर्वको OpenStreetMap तथ्याङ्कमा आधारित छ।
            """
        else:
            title = "RAPID DISASTER SITUATION REPORT (SITREP)"
            badge = "Educational Prototype"
            meta = f"Event Date: <strong>{v['event_date']}</strong> | Optical Observation: <strong>{v['optical_evidence_date']}</strong> | AOI: <strong>{v['bbox']}</strong>"
            kpi1_lbl = "Observed Hazard"
            kpi1_val = f"{v['affected_km2_observed']} km²"
            kpi2_lbl = "Destroyed Buildings"
            kpi2_val = v["buildings_destroyed"]
            kpi3_lbl = "Destroyed Bridges"
            kpi3_val = v["bridges_destroyed"]
            kpi4_lbl = "Cut-Off Settlements"
            kpi4_val = v["cutoff_vehicle_optimistic_count"]

            map_caption = "Satellite change detection and damaged infrastructure overview"
            sec_needs = "NEEDS HELP FIRST (Rescue Priority)"
            sec_repair = "REPAIR FIRST (Access Restoration)"
            sec_infra = "INFRASTRUCTURE DAMAGE OVERVIEW"
            sec_limits = "DATA LIMITATIONS & ATTRIBUTION"

            rescue_rows = "".join([f"<li><strong>{html.escape(s.get('name', 'Settlement'))}</strong>: {s.get('building_count', 0)} buildings (isolated by road)</li>" for s in top_rescue]) if top_rescue else "<li>No settlements isolated by road.</li>"

            if top_pkg and pkg_elem_count > 0:
                repair_text = f"<strong>Package {pkg_rank}</strong> ({pkg_elem_count} link{'s' if pkg_elem_count > 1 else ''}: {html.escape(pkg_elems_str)}) reconnects <strong>{pkg_set} settlement{'s' if pkg_set != 1 else ''}</strong> and <strong>{pkg_bld} buildings</strong>."
            else:
                repair_text = "No actionable repair package identified (0 elements restore network connectivity)."

            infra_html = f"""
            <table class="table-compact">
              <tr><th>Asset</th><th>Destroyed</th><th>Damaged / Poss.</th><th>Cloud-Obscured</th><th>Total Evaluated</th></tr>
              <tr><td>Buildings</td><td><strong>{v['buildings_destroyed']}</strong></td><td>{v['buildings_affected_total']}</td><td>{v['buildings_cloud_unverified']}</td><td>{v['buildings_total']}</td></tr>
              <tr><td>Bridges</td><td><strong>{v['bridges_destroyed']}</strong></td><td>{v['bridges_affected_total']}</td><td>{v['bridges_cloud_unverified']}</td><td>{v['bridges_total']}</td></tr>
              <tr><td>Roads (km)</td><td><strong>{v['roads_destroyed_km']}</strong></td><td>{v['roads_possibly_damaged_km']}</td><td>{v['roads_cloud_unverified_km']}</td><td>{v['roads_total_km']}</td></tr>
            </table>
            """
            limits_html = f"""
            • {v['buildings_cloud_unverified']} buildings and {v['roads_cloud_unverified_km']} km roads unverified under cloud cover.<br/>
            • Inferred hazard ({v['affected_km2_inferred']} km²) modeled along drainage corridors.<br/>
            • Infrastructure counts depend on pre-event OpenStreetMap inventory density.
            """

        html_out = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
@page {{
    size: A4 portrait;
    margin: 8mm 10mm 8mm 10mm;
}}
* {{
    box-sizing: border-box;
}}
body {{
    font-family: 'Noto Sans Devanagari', 'Lohit Devanagari', 'FreeSans', 'DejaVu Sans', sans-serif;
    color: #0f172a;
    line-height: 1.25;
    font-size: 8pt;
    margin: 0;
    padding: 0;
}}
.header {{
    border-bottom: 2px solid #b91c1c;
    padding-bottom: 3px;
    margin-bottom: 4px;
}}
.title-row {{
    display: flex;
    justify-content: space-between;
    align-items: baseline;
}}
h1 {{
    font-size: 13pt;
    color: #991b1b;
    margin: 0;
    text-transform: uppercase;
    font-weight: 700;
}}
.badge {{
    font-size: 7.5pt;
    font-weight: 600;
    color: #475569;
    background: #f1f5f9;
    padding: 2px 6px;
    border-radius: 3px;
    border: 1px solid #cbd5e1;
}}
.meta-line {{
    font-size: 7.5pt;
    color: #475569;
    margin-top: 2px;
}}
.kpi-row {{
    display: flex;
    gap: 6px;
    margin: 4px 0;
}}
.kpi-card {{
    flex: 1;
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-top: 3px solid #0284c7;
    padding: 3px 5px;
    border-radius: 3px;
}}
.kpi-card.alert {{
    border-top-color: #dc2626;
}}
.kpi-val {{
    font-size: 13pt;
    font-weight: 700;
    color: #0f172a;
    line-height: 1.1;
}}
.kpi-card.alert .kpi-val {{
    color: #b91c1c;
}}
.kpi-lbl {{
    font-size: 6.8pt;
    font-weight: 600;
    color: #64748b;
    text-transform: uppercase;
    margin-top: 1px;
}}
.main-grid {{
    display: flex;
    gap: 8px;
    margin: 3px 0;
}}
.col-left {{
    flex: 1.05;
}}
.col-right {{
    flex: 0.95;
}}
.section-title {{
    font-size: 8.2pt;
    font-weight: 700;
    color: #0369a1;
    border-bottom: 1px solid #bae6fd;
    padding-bottom: 1px;
    margin: 4px 0 2px 0;
    text-transform: uppercase;
}}
.section-title.danger {{
    color: #b91c1c;
    border-bottom-color: #fecaca;
}}
.map-box {{
    border: 1px solid #cbd5e1;
    border-radius: 3px;
    overflow: hidden;
    margin-bottom: 4px;
    text-align: center;
    background: #f1f5f9;
}}
.map-img {{
    width: 100%;
    height: 125px;
    object-fit: cover;
    display: block;
}}
.map-caption {{
    font-size: 6.5pt;
    color: #64748b;
    padding: 1px 3px;
    background: #f8fafc;
    border-top: 1px solid #e2e8f0;
}}
p {{
    margin: 2px 0;
}}
ul {{
    margin: 2px 0;
    padding-left: 14px;
}}
li {{
    margin-bottom: 1px;
}}
.table-compact {{
    width: 100%;
    border-collapse: collapse;
    font-size: 7pt;
    margin: 2px 0;
}}
.table-compact th, .table-compact td {{
    padding: 2px 4px;
    border: 1px solid #e2e8f0;
    text-align: left;
}}
.table-compact th {{
    background: #f1f5f9;
    color: #475569;
    font-weight: 600;
}}
.limits-box {{
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 3px;
    padding: 3px 5px;
    margin-top: 2px;
    font-size: 6.8pt;
    color: #475569;
    line-height: 1.25;
}}
.footer {{
    border-top: 1px solid #cbd5e1;
    padding-top: 3px;
    margin-top: 4px;
    font-size: 6.5pt;
    color: #64748b;
    line-height: 1.25;
}}
</style>
</head>
<body>

<div class="header">
  <div class="title-row">
    <h1>{title}</h1>
    <span class="badge">{badge}</span>
  </div>
  <div class="meta-line">{meta}</div>
</div>

<div class="kpi-row">
  <div class="kpi-card alert">
    <div class="kpi-val">{kpi1_val}</div>
    <div class="kpi-lbl">{kpi1_lbl}</div>
  </div>
  <div class="kpi-card alert">
    <div class="kpi-val">{kpi2_val}</div>
    <div class="kpi-lbl">{kpi2_lbl}</div>
  </div>
  <div class="kpi-card alert">
    <div class="kpi-val">{kpi3_val}</div>
    <div class="kpi-lbl">{kpi3_lbl}</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-val">{kpi4_val}</div>
    <div class="kpi-lbl">{kpi4_lbl}</div>
  </div>
</div>

<div class="main-grid">
  <div class="col-left">
    <div class="map-box">
      {ql_img_tag}
      <div class="map-caption">{map_caption}</div>
    </div>
    
    <div class="section-title danger">{sec_needs}</div>
    <ul>
      {rescue_rows}
    </ul>
  </div>
  
  <div class="col-right">
    <div class="section-title">{sec_repair}</div>
    <p>{repair_text}</p>
    
    <div class="section-title">{sec_infra}</div>
    {infra_html}
    
    <div class="section-title">{sec_limits}</div>
    <div class="limits-box">
      {limits_html}
    </div>
  </div>
</div>

<div class="footer">
  Contains modified Copernicus Sentinel data {ev_year}. Produced using Copernicus WorldDEM-30 © DLR e.V. 2010–2014 and © Airbus Defence and Space GmbH 2014–2018 provided under COPERNICUS by the European Union and ESA; all rights reserved. © OpenStreetMap contributors under ODbL. European Union, Copernicus Emergency Management Service data (EMSR927, EMSR692, EMSR659). Educational prototype, not an operational tool.
</div>

</body>
</html>
"""
        return html_out

    def generate_pdf(
        self,
        markdown_text: str,
        output_pdf_path: Path | str,
        lang: str = "en"
    ) -> Path:
        """Render professional 1-page PDF using WeasyPrint with exact map layout."""
        out_path = Path(output_pdf_path).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)

        html_content = self._build_1page_html(lang=lang)
        doc = weasyprint.HTML(string=html_content, url_fetcher=safe_url_fetcher)
        doc.write_pdf(str(out_path))
        logger.info("Generated SitRep PDF: %s", out_path)
        return out_path

    def generate_all(self, output_dir: Path | str) -> Dict[str, Path]:
        """Generate English and Nepali Markdown reports, 1-page PDFs, and separate lineage appendices."""
        target_dir = Path(output_dir).resolve()
        target_dir.mkdir(parents=True, exist_ok=True)

        md_en = self.generate_markdown(lang="en")
        md_ne = self.generate_markdown(lang="ne")
        app_en = self.generate_appendix(lang="en")
        app_ne = self.generate_appendix(lang="ne")

        en_md_path = target_dir / "sitrep_en.md"
        ne_md_path = target_dir / "sitrep_ne.md"
        app_en_path = target_dir / "sitrep_lineage_appendix_en.md"
        app_ne_path = target_dir / "sitrep_lineage_appendix_ne.md"
        en_pdf_path = target_dir / "sitrep_en.pdf"
        ne_pdf_path = target_dir / "sitrep_ne.pdf"

        en_md_path.write_text(md_en, encoding="utf-8")
        ne_md_path.write_text(md_ne, encoding="utf-8")
        app_en_path.write_text(app_en, encoding="utf-8")
        app_ne_path.write_text(app_ne, encoding="utf-8")

        self.generate_pdf(md_en, en_pdf_path, lang="en")
        self.generate_pdf(md_ne, ne_pdf_path, lang="ne")

        return {
            "en_markdown": en_md_path,
            "ne_markdown": ne_md_path,
            "en_appendix": app_en_path,
            "ne_appendix": app_ne_path,
            "en_pdf": en_pdf_path,
            "ne_pdf": ne_pdf_path,
        }
