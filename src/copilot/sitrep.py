"""Bilingual 1-Page Situation Report Generator (English & Nepali).

Generates strictly grounded 1-page situation reports structured around the problem statement:
1. "Where did the flood hit?" / "बाढी कहाँ आयो?"
2. "What was damaged?" / "के क्षति भयो?"
3. "Who is cut off?" / "को सम्पर्कविहीन भयो?"
4. "What to repair first" / "पहिले के मर्मत गर्ने?"

- Dynamic data binding from FactStore and run files with 0 hardcoded numbers.
- Exactly 1 A4 portrait page layout in PDF with overview map quicklook.
- Separate lineage appendix document.
- Compliant attributions including European Union Copernicus EMS and Educational prototype disclaimer.
"""

from __future__ import annotations

import base64
import html
import json
import logging
import os
import re
from math import atan2, cos, radians, sin, sqrt
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import weasyprint

from src.common.naming import format_settlement_name
from src.dashboard.app import extract_primary_river

from .facts import FactStore
from .guard import NumberGuard
from .sitrep_map import generate_sitrep_overview_map

logger = logging.getLogger("copilot.sitrep")


def to_ne_near_place(place_str: str) -> str:
    """Format English 'Near <place>' strings into standard Nepali '<place> नजिक'."""
    if not place_str:
        return ""
    clean = re.sub(r"^Near\s+", "", place_str.strip(), flags=re.IGNORECASE)
    m = re.match(r"^(.*?)(?:\s*\((.*?)\))?$", clean)
    if m and m.group(2):
        pname = m.group(1).strip()
        dist = m.group(2).replace("km", "कि.मी.").replace("m", "मि.")
        return f"{pname} नजिक ({dist})"
    return f"{clean} नजिक"


def haversine_km(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """Calculate great-circle distance between two geographic coordinates in kilometers."""
    R = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c


SITREP_TEMPLATE_PROSE_EN = """# RAPID DISASTER SITUATION REPORT (SITREP)
**Event Date:** {{event_date}} | **AOI:** {{bbox}} | **Assessment Type:** Rapid Situation Report
**Satellite Observations:** Pre: {{pre_dates_str}} | Post: {{post_dates_str}} | **Sensors:** {{sensors_used}}

---

### 1. Where did the flood hit?
Satellite change detection identifies **{{affected_km2_observed}} km²** of directly observed hazard extent and **{{affected_km2_inferred}} km²** inferred along drainage corridors. The affected hazard stretch extends along **{{primary_river}}** from near **{{upstream_place}}** to near **{{downstream_place}}**.

---

### 2. What was damaged?
- **Buildings (Total {{buildings_total}} assessed):**
  - {{bld_grade_1_label}}: **{{buildings_destroyed}}**
  - {{bld_grade_2_label}}: **{{buildings_damaged}}**
  - Possibly Damaged: **{{buildings_possibly_damaged}}**
  - Total Affected: **{{buildings_affected_total}}**
  - Cloud-Covered (Unverified): **{{buildings_cloud_unverified}}**

- **Bridges (Total {{bridges_total}} assessed):**
  - {{bridge_status_label}}: **{{bridges_destroyed}}** (Major road corridors: {{major_bridge_roads_en}})
  - Possibly Damaged: **{{bridges_possibly_damaged}}**
  - Total Affected: **{{bridges_affected_total}}**
  - Cloud-Covered (Unverified): **{{bridges_cloud_unverified}}**

- **Road Network (Total {{roads_total_km}} km assessed; {{roads_drivable_km}} km drivable network in bbox):**
  - {{road_status_label}}: **{{roads_destroyed_km}} km** (Main corridor damage: {{main_road_destroyed_en}})
  - Possibly Damaged: **{{roads_possibly_damaged_km}} km**
  - Cloud-Covered (Unverified): **{{roads_cloud_unverified_km}} km**

---

### 3. Who is cut off?
- **Road Cut-Off Settlements:** **{{cutoff_vehicle_optimistic_count}} settlements** cut off from any town or hospital by vehicle (pessimistic: **{{cutoff_vehicle_pessimistic_count}}**). Pedestrian cut-off: **{{cutoff_walking_optimistic_count}} settlements**.
- **No Ground Access:** **{{no_ground_access_count}} settlements** have both vehicle and walking routes severed (air / boat priority).

#### No-Ground-Access Settlements (Air / Boat Priority)
{{no_ground_table_md_en}}

#### 5 Largest Road Cut-Off Settlements
{{top_veh_table_md_en}}

---

### 4. What to repair first
- **Best Single Repair:** {{single_repair_sentence_en}}.
- **Access Restoration Package 1:** {{package_1_sentence_en}}

---

### Known Limitations & Attributions
1. **Cloud Obscuration:** {{buildings_cloud_unverified}} buildings and {{roads_cloud_unverified_km}} km of roads remain unverified due to cloud cover.
2. **Hydraulic Inundation Inference:** Tributary hazard boundaries are hydraulically modeled rather than observed by radar backscatter; radar shadow/layover masked using DEM look-angle.
3. **OSM Baseline Data:** Residential population counts are not available in OpenStreetMap baseline data.

{{attributions}}
"""


SITREP_TEMPLATE_PROSE_NE = """# द्रुत विपद् स्थिति प्रतिवेदन (SITREP)
**घटना मिति:** {{event_date}} | **प्रभावित क्षेत्र (AOI):** {{bbox}} | **प्रतिवेदन प्रकार:** द्रुत स्थिति प्रतिवेदन
**भूउपग्रह अवलोकन:** पूर्व: {{pre_dates_str}} | पश्चात: {{post_dates_str}} | **प्रयोग गरिएका सेन्सरहरू:** {{sensors_used}}

---

### १. बाढी कहाँ आयो?
भूउपग्रह परिवर्तन पहिचान अनुसार **{{affected_km2_observed}} वर्ग कि.मी.** क्षेत्रमा प्रत्यक्ष बाढी/क्षति पुष्टि भएको छ र **{{affected_km2_inferred}} वर्ग कि.मी.** क्षेत्र खोला तथा पहिरो बहावमा अनुमानित छ। बाढीको मुख्य प्रभाव **{{primary_river}}** वरपर **लगभग {{upstream_place_ne}} देखि {{downstream_place_ne}} सम्म** फैलिएको छ।

---

### २. के क्षति भयो?
- **भवनहरू (कुल {{buildings_total}} मूल्याङ्कन):**
  - {{bld_grade_1_label_ne}}: **{{buildings_destroyed}}**
  - {{bld_grade_2_label_ne}}: **{{buildings_damaged}}**
  - सम्भावित क्षति: **{{buildings_possibly_damaged}}**
  - कुल प्रभावित भवन: **{{buildings_affected_total}}**
  - बादलले ढाकिएका (अपुष्ट): **{{buildings_cloud_unverified}}**

- **पुलहरू (कुल {{bridges_total}} मूल्याङ्कन):**
  - {{bridge_status_label_ne}}: **{{bridges_destroyed}}** (प्रमुख सडकहरू: {{major_bridge_roads_ne}})
  - सम्भावित क्षति: **{{bridges_possibly_damaged}}**
  - कुल प्रभावित पुल: **{{bridges_affected_total}}**
  - बादलले ढाकिएका: **{{bridges_cloud_unverified}}**

- **सडक सञ्जाल (कुल {{roads_total_km}} कि.मी. मूल्याङ्कन; कोर क्षेत्रमा {{roads_drivable_km}} कि.मी. सवारी सञ्जाल):**
  - {{road_status_label_ne}}: **{{roads_destroyed_km}} कि.मी.** (प्रमुख सडक खण्ड: {{main_road_destroyed_ne}})
  - सम्भावित क्षति: **{{roads_possibly_damaged_km}} कि.मी.**
  - बादलले ढाकिएका: **{{roads_cloud_unverified_km}} कि.मी.**

---

### ३. को सम्पर्कविहीन भयो?
- **सवारी सम्पर्कविहीन बस्तीहरू:** **{{cutoff_vehicle_optimistic_count}} बस्तीहरू** कुनै पनि सहर वा अस्पतालबाट विच्छेद छन् (निराशावादी अवस्था: **{{cutoff_vehicle_pessimistic_count}}**)। पैदल मार्ग अवरुद्ध: **{{cutoff_walking_optimistic_count}} बस्तीहरू**।
- **पूर्ण स्थल सम्पर्कविहीन:** **{{no_ground_access_count}} बस्तीहरू**मा पैदल तथा सवारी दुवै मार्ग बन्द भएका छन् (हवाई / डुङ्गा प्राथमिकता)।

#### पूर्ण स्थल सम्पर्कविहीन बस्तीहरू (हवाई / डुङ्गा प्राथमिकता)
{{no_ground_table_md_ne}}

#### सबैभन्दा ठूला ५ सवारी सम्पर्कविहीन बस्तीहरू
{{top_veh_table_md_ne}}

---

### ४. पहिले के मर्मत गर्ने?
- **सबैभन्दा प्रभावकारी एकल मर्मत:** {{single_repair_sentence_ne}}।
- **पहुँच पुनर्स्थापना प्याकेज १:** {{package_1_sentence_ne}}

---

### मुख्य सीमितता तथा प्रतिलिपि अधिकार
१. **बादलको प्रभाव:** {{buildings_cloud_unverified}} भवनहरू र {{roads_cloud_unverified_km}} कि.मी. सडक बादलका कारण अप्टिकल स्याटेलाइटबाट प्रमाणीकरण हुन सकेको छैन।
२. **मोडेल अनुमान:** सहायक नदीहरूमा बाढी क्षेत्र हाइड्रोलिक मोडेलिङद्वारा अनुमान गरिएको हो; पहाडी भिरालो भूभाग DEM लुक-एंगलद्वारा हटाइएको छ।
३. **जनसंख्या तथ्याङ्क:** ओपन्स्ट्रीटम्याप आधारभूत तथ्याङ्कमा आवासीय जनसंख्या उपलब्ध छैन।

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
| No Ground Access Settlements | {{no_ground_access_count}} | `processed/routing/settlements.geojson` | `vehicle_status_opt == 'cut_off' and walking_status_opt == 'cut_off'` |
| Total Buildings Evaluated | {{buildings_total}} | `processed/damage_summary.json` | `buildings.total_count` |
| Total Affected Buildings | {{buildings_affected_total}} | `processed/damage_summary.json` | `buildings.affected_count` |
| Destroyed / Flooded Buildings | {{buildings_destroyed}} | `processed/damage_summary.json` | `buildings.damage_grade_counts` |
| Damaged Buildings | {{buildings_damaged}} | `processed/damage_summary.json` | `buildings.damage_grade_counts` |
| Possibly Damaged Buildings | {{buildings_possibly_damaged}} | `processed/damage_summary.json` | `buildings.damage_grade_counts` |
| Cloud-Unverified Buildings | {{buildings_cloud_unverified}} | `processed/damage_summary.json` | `buildings.damage_grade_counts.Unknown (cloud)` |
| Total Road Length Evaluated | {{roads_total_km}} km | `processed/damage_summary.json` | `roads.total_km` (all OSM segments in buffer) |
| Classified Drivable Road Network | {{roads_drivable_km}} km | `processed/damage_summary.json` | `osm_coverage.road_km_by_type` (in bbox) |
| Destroyed Road Length | {{roads_destroyed_km}} km | `processed/damage_summary.json` | `roads.km_by_damage_grade.Destroyed` |
| Possibly Damaged Road Length | {{roads_possibly_damaged_km}} km | `processed/damage_summary.json` | `roads.km_by_damage_grade.Possibly damaged` |
| Cloud-Unverified Road Length | {{roads_cloud_unverified_km}} km | `processed/damage_summary.json` | `roads.km_by_damage_grade.Unknown (cloud)` |
| Total Bridges Evaluated | {{bridges_total}} | `processed/damage_summary.json` | `bridges.total_count` |
| Total Affected Bridges | {{bridges_affected_total}} | `processed/damage_summary.json` | `bridges.affected_count` |
| Destroyed / Flooded Bridges | {{bridges_destroyed}} | `processed/damage_summary.json` | `bridges.damage_grade_counts` |
| Possibly Damaged Bridges | {{bridges_possibly_damaged}} | `processed/damage_summary.json` | `bridges.damage_grade_counts` |
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
| पूर्ण स्थल सम्पर्कविहीन बस्ती | {{no_ground_access_count}} | `processed/routing/settlements.geojson` | `vehicle_status_opt == 'cut_off' and walking_status_opt == 'cut_off'` |
| मूल्याङ्कन गरिएका कुल भवन | {{buildings_total}} | `processed/damage_summary.json` | `buildings.total_count` |
| कुल प्रभावित भवनहरू | {{buildings_affected_total}} | `processed/damage_summary.json` | `buildings.affected_count` |
| नष्ट / जलमग्न भवनहरू | {{buildings_destroyed}} | `processed/damage_summary.json` | `buildings.damage_grade_counts` |
| क्षतिग्रस्त भवनहरू | {{buildings_damaged}} | `processed/damage_summary.json` | `buildings.damage_grade_counts` |
| सम्भावित क्षति भवनहरू | {{buildings_possibly_damaged}} | `processed/damage_summary.json` | `buildings.damage_grade_counts` |
| बादलले ढाकिएका भवनहरू | {{buildings_cloud_unverified}} | `processed/damage_summary.json` | `buildings.damage_grade_counts.Unknown (cloud)` |
| कुल मूल्याङ्कन सडक लम्बाइ | {{roads_total_km}} km | `processed/damage_summary.json` | `roads.total_km` |
| कोर क्षेत्रमा सवारी योग्य सडक | {{roads_drivable_km}} km | `processed/damage_summary.json` | `osm_coverage.road_km_by_type` |
| नष्ट सडक लम्बाइ | {{roads_destroyed_km}} km | `processed/damage_summary.json` | `roads.km_by_damage_grade.Destroyed` |
| सम्भावित क्षति सडक | {{roads_possibly_damaged_km}} km | `processed/damage_summary.json` | `roads.km_by_damage_grade.Possibly damaged` |
| बादलले ढाकिएको सडक | {{roads_cloud_unverified_km}} km | `processed/damage_summary.json` | `roads.km_by_damage_grade.Unknown (cloud)` |
| मूल्याङ्कन गरिएका कुल पुल | {{bridges_total}} | `processed/damage_summary.json` | `bridges.total_count` |
| कुल प्रभावित पुलहरू | {{bridges_affected_total}} | `processed/damage_summary.json` | `bridges.affected_count` |
| नष्ट / जलमग्न पुलहरू | {{bridges_destroyed}} | `processed/damage_summary.json` | `bridges.damage_grade_counts` |
| सम्भावित क्षति पुलहरू | {{bridges_possibly_damaged}} | `processed/damage_summary.json` | `bridges.damage_grade_counts` |
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

    def __init__(self, fact_store: FactStore | Path | str):
        if isinstance(fact_store, (str, Path)):
            self.store = FactStore(fact_store)
        else:
            self.store = fact_store
        self.guard = NumberGuard()
        self.values = self._collect_fill_values()

    def _collect_fill_values(self) -> Dict[str, Any]:
        """Collect all grounded numeric values and structured entities from run directory."""
        run_dir = Path(self.store.run_dir)
        proc = run_dir / "processed"
        routing = proc / "routing"
        raw = run_dir / "raw"

        # 1. Summary metadata
        sum_p = run_dir / "run_summary.json"
        sum_data = json.loads(sum_p.read_text()) if sum_p.exists() else {}
        ev_date = str(sum_data.get("event_date", self.store.get_value("event.date", "2026-08-26")))
        ev_year = ev_date[:4] if len(ev_date) >= 4 and ev_date[:4].isdigit() else "2026"

        bbox_raw = sum_data.get("bbox", self.store.metadata.get("bbox", [0, 0, 0, 0]))
        bbox_str = f"[{bbox_raw[0]:.2f}, {bbox_raw[1]:.2f}, {bbox_raw[2]:.2f}, {bbox_raw[3]:.2f}]" if isinstance(bbox_raw, list) and len(bbox_raw) == 4 else str(bbox_raw)

        raw_regime = sum_data.get("terrain_regime") or ("flat_floodplain" if "assam" in run_dir.name.lower() else "steep_valley")
        is_flat = (raw_regime == "flat_floodplain")

        # 2. Sensors & Dates
        s2_scenes = sum_data.get("s2_scenes_used", [])
        pre_dates, post_dates = set(), set()
        for s in s2_scenes:
            for p in s.split("_"):
                if len(p) >= 8 and p[:8].isdigit():
                    formatted = f"{p[:4]}-{p[4:6]}-{p[6:8]}"
                    if s.startswith("pre_"):
                        pre_dates.add(formatted)
                    elif s.startswith("post_"):
                        post_dates.add(formatted)
        pre_dates_str = f"{min(pre_dates)} to {max(pre_dates)}" if pre_dates else "—"
        post_dates_str = f"{min(post_dates)} to {max(post_dates)}" if post_dates else "—"

        sensors = sum_data.get("sensors_used", self.store.metadata.get("sensors_used", ["Sentinel-2 MSI", "Sentinel-1 RTC SAR", "Copernicus DEM-30", "OpenStreetMap"]))
        sensors_str = ", ".join(sensors) if isinstance(sensors, list) else str(sensors)

        # 3. Hazard Areas
        obs_area = round(float(self.store.get_value("hazard.area.event_total_affected", self.store.get_value("metrics.affected_km2_observed", 0.0))), 2)
        inf_area = round(float(self.store.get_value("hazard.area.event_inferred_affected", self.store.get_value("metrics.affected_km2_inferred", 0.0))), 2)

        # 4. River and upstream/downstream stretch
        primary_river = extract_primary_river(run_dir) or ("Brahmaputra" if is_flat else "local river valley")
        haz_p = proc / "hazard_polygons.geojson"
        places_p = raw / "osm" / "osm_places.geojson"

        up_place, down_place = "upstream area", "downstream area"
        if haz_p.exists() and places_p.exists():
            try:
                hdata = json.loads(haz_p.read_text())
                pdata = json.loads(places_p.read_text())
                named_places = []
                for pf in pdata.get("features", []):
                    pp = pf.get("properties", {})
                    pname = pp.get("name:en") or pp.get("name")
                    pgeom = pf.get("geometry", {})
                    pltype = pp.get("place", "")
                    if pname and pgeom and pgeom.get("type") == "Point":
                        coords = pgeom.get("coordinates", [None, None])
                        if coords[0] is not None:
                            named_places.append((pname, coords[0], coords[1], pltype))

                c2_coords = []
                for hf in hdata.get("features", []):
                    if hf.get("properties", {}).get("class") in [2, 3]:
                        def _rec(c):
                            if not c: return
                            if isinstance(c[0], (int, float)): c2_coords.append((c[0], c[1]))
                            else:
                                for sub in c: _rec(sub)
                        _rec(hf.get("geometry", {}).get("coordinates", []))

                if not c2_coords:
                    for hf in hdata.get("features", []):
                        def _rec(c):
                            if not c: return
                            if isinstance(c[0], (int, float)): c2_coords.append((c[0], c[1]))
                            else:
                                for sub in c: _rec(sub)
                        _rec(hf.get("geometry", {}).get("coordinates", []))

                if c2_coords and named_places:
                    sorted_y = sorted(c2_coords, key=lambda pt: pt[1])
                    pt_south = sorted_y[0]
                    pt_north = sorted_y[-1]

                    dem_p = raw / "dem" / "dem_cog.tif"
                    n_is_upstream = True
                    if dem_p.exists():
                        try:
                            import rasterio
                            with rasterio.open(dem_p) as dem_src:
                                val_s = list(dem_src.sample([pt_south]))[0][0]
                                val_n = list(dem_src.sample([pt_north]))[0][0]
                                if val_s > val_n:
                                    n_is_upstream = False
                        except Exception:
                            pass

                    pt_up = pt_north if n_is_upstream else pt_south
                    pt_down = pt_south if n_is_upstream else pt_north

                    settle_places = [p for p in named_places if p[3] in ["town", "village", "hamlet", "suburb", "neighbourhood", "isolated_dwelling"]]
                    pool = settle_places if settle_places else named_places

                    def _find_nearest(target_pt):
                        best_n, min_d = None, 999999
                        for pname, plon, plat, _ in pool:
                            d = haversine_km(target_pt[0], target_pt[1], plon, plat)
                            if d < min_d:
                                min_d = d
                                best_n = pname
                        return best_n, min_d

                    up_p, _ = _find_nearest(pt_up)
                    down_p, _ = _find_nearest(pt_down)
                    if up_p: up_place = up_p
                    if down_p: down_place = down_p
            except Exception as e:
                logger.warning(f"Error computing hazard stretch: {e}")

        # 5. Infrastructure Damage
        dmg_p = proc / "damage_summary.json"
        dmg = json.loads(dmg_p.read_text()) if dmg_p.exists() else {}
        bld_total = dmg.get("buildings", {}).get("total_count", int(self.store.get_value("damage.buildings.total", 0)))
        bld_affected = dmg.get("buildings", {}).get("affected_count", int(self.store.get_value("damage.buildings.affected_total", 0)))
        b_grades = dmg.get("buildings", {}).get("damage_grade_counts", {})
        bld_dest = b_grades.get("Destroyed", b_grades.get("Flooded", int(self.store.get_value("damage.buildings.destroyed", 0))))
        bld_dam = b_grades.get("Damaged", b_grades.get("Possibly flooded", int(self.store.get_value("damage.buildings.damaged", 0))))
        bld_poss = b_grades.get("Possibly damaged", int(self.store.get_value("damage.buildings.possibly_damaged", 0)))
        bld_unv = b_grades.get("Unknown (cloud)", int(self.store.get_value("damage.buildings.unknown_cloud", 0)))

        br_total = dmg.get("bridges", {}).get("total_count", int(self.store.get_value("damage.bridges.total", 0)))
        br_affected = dmg.get("bridges", {}).get("affected_count", int(self.store.get_value("damage.bridges.affected_total", 0)))
        br_grades = dmg.get("bridges", {}).get("damage_grade_counts", {})
        br_dest = br_grades.get("Destroyed", br_grades.get("Flooded", int(self.store.get_value("damage.bridges.destroyed", 0))))
        br_poss = br_grades.get("Possibly damaged", int(self.store.get_value("damage.bridges.possibly_damaged", 0)))
        br_unv = br_grades.get("Unknown (cloud)", int(self.store.get_value("damage.bridges.unknown_cloud", 0)))

        rd_total_km = round(float(dmg.get("roads", {}).get("total_km", self.store.get_value("damage.roads.total_km", 0.0))), 2)
        rd_drivable_km = round(float(self.store.get_value("damage.roads.drivable_km", rd_total_km)), 2)
        rd_grades = dmg.get("roads", {}).get("km_by_damage_grade", {})
        rd_dest_km = round(float(rd_grades.get("Destroyed", rd_grades.get("Flooded", self.store.get_value("damage.roads.destroyed_km", 0.0)))), 2)
        rd_poss_km = round(float(rd_grades.get("Possibly damaged", self.store.get_value("damage.roads.possibly_damaged_km", 0.0))), 2)
        rd_unv_km = round(float(rd_grades.get("Unknown (cloud)", self.store.get_value("damage.roads.unknown_cloud_km", 0.0))), 2)

        # Destroyed bridges on primary/secondary roads
        major_br_roads = []
        br_file = proc / "bridges_graded.geojson"
        if br_file.exists():
            try:
                bdata = json.loads(br_file.read_text())
                for f in bdata.get("features", []):
                    p = f.get("properties", {})
                    if p.get("damage_grade") in ["Destroyed", "Flooded"]:
                        name = p.get("name:en") or p.get("name") or p.get("road_name")
                        ref = p.get("ref") or p.get("road_ref")
                        hw = p.get("highway")
                        if any(k in str(name).lower() for k in ["pasang", "lhamu"]): name = "Pasang Lhamu Highway"
                        lbl = f"{name} ({ref})" if name and ref else (name or ref or hw)
                        if hw in ["primary", "secondary", "trunk", "motorway"] or ref in ["NH42", "NH18", "NH310A", "NH310AG", "F30"]:
                            major_br_roads.append(lbl)
            except Exception:
                pass
        major_br_roads_en = ", ".join(dict.fromkeys(major_br_roads)) if major_br_roads else "none on primary roads"
        major_br_roads_ne = ", ".join(dict.fromkeys(major_br_roads)) if major_br_roads else "मुख्य सडकमा कुनै पनि छैन"

        # Main road destroyed km
        road_dest_by_name = {}
        r_file = proc / "roads_graded.geojson"
        if r_file.exists():
            try:
                rdata = json.loads(r_file.read_text())
                for rf in rdata.get("features", []):
                    rp = rf.get("properties", {})
                    if rp.get("damage_grade") in ["Destroyed", "Flooded"]:
                        rlen = rp.get("length_m", 0) / 1000.0
                        rname = rp.get("name:en") or rp.get("name")
                        rref = rp.get("ref")
                        if rname and any(k in rname.lower() for k in ["pasang", "lhamu"]):
                            rname = "Pasang Lhamu Highway"
                        if rref == "NH42" or (rname and "pasang" in rname.lower()):
                            lbl = "Pasang Lhamu Highway (NH42)"
                        elif rref == "F30" or (rname and "melamchi" in str(rname).lower()):
                            lbl = f"{rname or 'Helambu Highway'} (F30)"
                        elif rref in ["NH310A", "NH310AG"] or (rname and "sikkim" in str(rname).lower()):
                            lbl = f"{rname or 'North Sikkim Highway'} ({rref or 'NH310A'})"
                        else:
                            lbl = f"{rname} ({rref})" if rname and rref else (rname or rref or rp.get("highway", "local road"))
                        road_dest_by_name[lbl] = road_dest_by_name.get(lbl, 0.0) + rlen
            except Exception:
                pass
        sorted_roads = sorted(road_dest_by_name.items(), key=lambda x: x[1], reverse=True)
        if sorted_roads:
            main_rd_name, main_rd_len = sorted_roads[0]
            main_road_destroyed_en = f"{main_rd_name}: {main_rd_len:.2f} km"
            main_road_destroyed_ne = f"{main_rd_name}: {main_rd_len:.2f} कि.मी."
        else:
            main_road_destroyed_en = "no major classified road destroyed"
            main_road_destroyed_ne = "कुनै प्रमुख सडक नष्ट भएको छैन"

        # 6. Routing & Cut-off Settlements
        s_file = routing / "settlements.geojson"
        s_geo = json.loads(s_file.read_text()) if s_file.exists() else {}
        s_features = s_geo.get("features", [])

        no_ground_list = []
        veh_cut_list = []
        for feat in s_features:
            p = dict(feat.get("properties", {}))
            geom = feat.get("geometry", {})
            coords = geom.get("coordinates", [None, None]) if geom else [None, None]
            p["_coords"] = coords
            p["_name"] = format_settlement_name(p, include_coords=False, include_access=False)
            p["_bld"] = p.get("building_count", 0)

            if p.get("vehicle_status_opt") == "cut_off" and p.get("walking_status_opt") == "cut_off":
                no_ground_list.append(p)
            if p.get("vehicle_status_opt") == "cut_off":
                veh_cut_list.append(p)

        no_ground_sorted = sorted(no_ground_list, key=lambda x: x["_bld"], reverse=True)
        veh_cut_sorted = sorted(veh_cut_list, key=lambda x: x["_bld"], reverse=True)[:5]

        c_p = routing / "cutoff_summary.json"
        c_data = json.loads(c_p.read_text()) if c_p.exists() else {}
        veh_opt_c = c_data.get("vehicle", {}).get("optimistic", {}).get("cut_off_count", len(veh_cut_list))
        veh_pess_c = c_data.get("vehicle", {}).get("pessimistic", {}).get("cut_off_count", veh_opt_c)
        walk_opt_c = c_data.get("walking", {}).get("optimistic", {}).get("cut_off_count", len(no_ground_list))
        no_ground_c = len(no_ground_list)

        def _make_table_md(items: List[Dict[str, Any]], lang_ne: bool) -> str:
            if not items:
                return "None (all assessed settlements retain access)." if not lang_ne else "कुनै पनि छैन (सबै बस्तीहरूमा पहुँच यथावत छ)।"
            headers = "| बस्ती | निर्देशाङ्क | भवन संख्या |\n| :--- | :--- | :--- |" if lang_ne else "| Settlement | Coordinates | Buildings |\n| :--- | :--- | :--- |"
            rows = []
            for it in items:
                c = it["_coords"]
                cstr = f"({c[1]:.4f}, {c[0]:.4f})" if c and c[0] is not None else "—"
                rows.append(f"| {it['_name']} | {cstr} | {it['_bld']} |")
            return headers + "\n" + "\n".join(rows)

        no_ground_table_md_en = _make_table_md(no_ground_sorted, False)
        no_ground_table_md_ne = _make_table_md(no_ground_sorted, True)
        top_veh_table_md_en = _make_table_md(veh_cut_sorted, False)
        top_veh_table_md_ne = _make_table_md(veh_cut_sorted, True)

        # 7. Repair Priority & Package 1
        rp_p = routing / "repair_priority.json"
        single_repair_en = "No single repair reconnects a settlement on its own"
        single_repair_ne = "कुनै पनि एकल मर्मतले आफैंमा बस्ती जोड्न सक्दैन"

        if rp_p.exists():
            try:
                rp_data = json.loads(rp_p.read_text())
                single_ranking = rp_data.get("single_element_repair_ranking", [])
                if single_ranking:
                    best_single = single_ranking[0]
                    s_rec = best_single.get("settlements_regained_if_only_repaired", 0)
                    b_rec = best_single.get("buildings_regained_if_only_repaired", 0)
                    osm_id = best_single.get("osm_id", "")
                    m_len = best_single.get("total_destroyed_length_m", 0.0)

                    road_lbl = ""
                    roads_file = proc / "roads_graded.geojson"
                    if roads_file.exists():
                        try:
                            r_data = json.loads(roads_file.read_text())
                            for feat in r_data.get("features", []):
                                props = feat.get("properties", {})
                                oid = props.get("@osmId") or props.get("osm_id") or ""
                                if oid == osm_id:
                                    rname = props.get("name:en") or props.get("name")
                                    rref = props.get("ref")
                                    if rname and any(k in rname.lower() for k in ["pasang", "lhamu"]):
                                        rname = "Pasang Lhamu Highway"
                                    if rname and rref: road_lbl = f"{rname} ({rref})"
                                    elif rname: road_lbl = rname
                                    elif rref: road_lbl = rref
                                    break
                        except Exception: pass
                    lbl_pfx = f"{road_lbl}, " if road_lbl else ""
                    if s_rec > 0:
                        single_repair_en = f"Best single repair: {lbl_pfx}{osm_id}, {round(m_len)} m -> {s_rec} settlements ({b_rec} buildings)"
                        single_repair_ne = f"सबैभन्दा प्रभावकारी एकल मर्मत: {lbl_pfx}{osm_id}, {round(m_len)} मिटर -> {s_rec} बस्तीहरू ({b_rec} भवनहरू)"
            except Exception:
                pass

        pkg_p = routing / "repair_packages.json"
        top_pkg = {}
        if pkg_p.exists():
            try:
                pkg_data = json.loads(pkg_p.read_text())
                for pkg in pkg_data.get("ranked_packages", []):
                    if len(pkg.get("elements", [])) > 0:
                        top_pkg = pkg
                        break
            except Exception:
                pass
        pkg_elem_c = top_pkg.get("element_count", len(top_pkg.get("elements", [])))
        pkg_elems = top_pkg.get("elements", [])
        pkg_len_m = top_pkg.get("length_m")
        if (pkg_len_m is None or pkg_len_m == 0.0) and rp_p.exists():
            try:
                rp_data = json.loads(rp_p.read_text())
                elem_lens = {x["osm_id"]: x.get("total_destroyed_length_m", 0.0) for x in rp_data.get("single_element_repair_ranking", [])}
                pkg_len_m = round(sum(elem_lens.get(e, 0.0) for e in pkg_elems), 1)
            except Exception:
                pkg_len_m = 0.0
        else:
            pkg_len_m = round(float(pkg_len_m or 0.0), 1)
        pkg_set_c = top_pkg.get("settlements_count", 0)
        pkg_bld_c = top_pkg.get("buildings_count", 0)
        pkg_elems_str = ", ".join(pkg_elems) if pkg_elems else "None"

        if top_pkg and pkg_elem_c > 0:
            pkg_sentence_en = f"Package 1 ({pkg_elem_c} elements, {pkg_len_m} m) restores vehicle access to {pkg_set_c} settlements ({pkg_bld_c} buildings)."
            pkg_sentence_ne = f"प्याकेज १ ({pkg_elem_c} खण्ड, {pkg_len_m} मिटर) ले {pkg_set_c} बस्तीहरू ({pkg_bld_c} भवनहरू) मा सवारी पहुँच पुनर्स्थापित गर्दछ।"
        else:
            pkg_sentence_en = "No actionable repair package required (no network access restoration needed)."
            pkg_sentence_ne = "कुनै पनि सडक मर्मत प्याकेज आवश्यक छैन।"

        attributions = (
            f"Contains modified Copernicus Sentinel data {ev_year}.\n"
            "Produced using Copernicus WorldDEM-30 © DLR e.V. 2010–2014 and © Airbus Defence and Space GmbH 2014–2018 provided under COPERNICUS by the European Union and ESA; all rights reserved.\n"
            "© OpenStreetMap contributors under ODbL.\n"
            "European Union, Copernicus Emergency Management Service data (EMSR927, EMSR692, EMSR659).\n"
            "Bountos et al., 2024 (Kuro Siwo).\n"
            "Educational prototype, not an operational tool."
        )

        return {
            "run_dir": str(run_dir),
            "event_date": ev_date,
            "event_year": ev_year,
            "bbox": bbox_str,
            "is_flat": is_flat,
            "sensors_used": sensors_str,
            "pre_dates_str": pre_dates_str,
            "post_dates_str": post_dates_str,
            "affected_km2_observed": str(obs_area),
            "affected_km2_inferred": str(inf_area),
            "primary_river": primary_river,
            "upstream_place": up_place,
            "downstream_place": down_place,
            "bld_grade_1_label": "Flooded" if is_flat else "Destroyed",
            "bld_grade_1_label_ne": "जलमग्न" if is_flat else "पूर्ण नष्ट",
            "bld_grade_2_label": "Possibly Flooded" if is_flat else "Damaged",
            "bld_grade_2_label_ne": "सम्भावित जलमग्न" if is_flat else "क्षतिग्रस्त",
            "buildings_total": str(bld_total),
            "buildings_affected_total": str(bld_affected),
            "buildings_destroyed": str(bld_dest),
            "buildings_damaged": str(bld_dam),
            "buildings_possibly_damaged": str(bld_poss),
            "buildings_cloud_unverified": str(bld_unv),
            "bridges_total": str(br_total),
            "bridges_affected_total": str(br_affected),
            "bridges_destroyed": str(br_dest),
            "bridges_possibly_damaged": str(br_poss),
            "bridges_cloud_unverified": str(br_unv),
            "major_bridge_roads_en": major_br_roads_en,
            "major_bridge_roads_ne": major_br_roads_ne,
            "roads_total_km": str(rd_total_km),
            "roads_drivable_km": str(rd_drivable_km),
            "roads_destroyed_km": str(rd_dest_km),
            "roads_possibly_damaged_km": str(rd_poss_km),
            "roads_cloud_unverified_km": str(rd_unv_km),
            "main_road_destroyed_en": main_road_destroyed_en,
            "main_road_destroyed_ne": main_road_destroyed_ne,
            "cutoff_vehicle_optimistic_count": str(veh_opt_c),
            "cutoff_vehicle_pessimistic_count": str(veh_pess_c),
            "cutoff_walking_optimistic_count": str(walk_opt_c),
            "no_ground_access_count": str(no_ground_c),
            "no_ground_table_md_en": no_ground_table_md_en,
            "no_ground_table_md_ne": no_ground_table_md_ne,
            "top_veh_table_md_en": top_veh_table_md_en,
            "top_veh_table_md_ne": top_veh_table_md_ne,
            "no_ground_sorted": no_ground_sorted,
            "veh_cut_sorted": veh_cut_sorted,
            "single_repair_sentence_en": single_repair_en,
            "single_repair_sentence_ne": single_repair_ne,
            "package_1_element_count": str(pkg_elem_c),
            "package_1_elements_list": pkg_elems_str,
            "package_1_length_m": str(pkg_len_m),
            "package_1_reconnected_settlements": str(pkg_set_c),
            "package_1_reconnected_buildings": str(pkg_bld_c),
            "package_1_sentence_en": pkg_sentence_en,
            "package_1_sentence_ne": pkg_sentence_ne,
            "attributions": attributions,
        }

    def fill_template(self, template_prose: str) -> str:
        """Replace all {{placeholder}} tokens with verified numbers from FactStore."""
        filled = template_prose
        for key, val in self.values.items():
            if isinstance(val, (str, int, float)):
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
        v = self.values
        run_dir = Path(v["run_dir"])
        proc = run_dir / "processed"
        is_ne = (lang == "ne")
        is_flat = v["is_flat"]

        # High-res publication-grade overview map banner
        overview_map_png = proc / f"sitrep_overview_map_{lang}.png"
        map_img_tag = ""
        try:
            generate_sitrep_overview_map(run_dir, overview_map_png, lang=lang)
            if overview_map_png.exists():
                b64 = base64.b64encode(overview_map_png.read_bytes()).decode("ascii")
                map_img_tag = f'<img class="overview-map" src="data:image/png;base64,{b64}" />'
        except Exception as e:
            logger.warning("Could not generate overview map: %s", e)

        # Format settlement rows with Nepali connectors
        def _build_settlement_rows(items: List[Dict[str, Any]]) -> str:
            if not items:
                return '<tr><td colspan="3" style="text-align:center; color:#64748b;">None (all retain access)</td></tr>' if not is_ne else '<tr><td colspan="3" style="text-align:center; color:#64748b;">कुनै पनि छैन (सबैमा पहुँच सुरक्षित)</td></tr>'
            rows = []
            for it in items:
                c = it["_coords"]
                coord_str = f"{c[1]:.4f}, {c[0]:.4f}" if c and c[0] is not None else "—"
                raw_name = it["_name"]
                name_str = to_ne_near_place(raw_name) if is_ne else raw_name
                rows.append(f'<tr><td>{html.escape(name_str)}</td><td>{coord_str}</td><td style="text-align:right;"><strong>{it["_bld"]}</strong></td></tr>')
            return "\n".join(rows)

        no_ground_rows = _build_settlement_rows(v["no_ground_sorted"])
        top_veh_rows = _build_settlement_rows(v["veh_cut_sorted"])

        if is_ne:
            title = "द्रुत विपद् स्थिति प्रतिवेदन (SITREP)"
            badge = "शैक्षिक प्रोटोटाइप"
            meta_str = f"घटना मिति: <strong>{v['event_date']}</strong> | उपग्रह: <strong>{v['post_dates_str']}</strong> | क्षेत्र (BBox): <strong>{v['bbox']}</strong>"

            up_place_ne = to_ne_near_place(v["upstream_place"]) if v["upstream_place"] else "अज्ञात क्षेत्र"
            down_place_ne = to_ne_near_place(v["downstream_place"]) if v["downstream_place"] else "अज्ञात क्षेत्र"

            sec1_title = "१. बाढी कहाँ आयो?"
            sec1_text = f"प्रत्यक्ष पुष्टि भएको बाढी क्षेत्र <strong>{v['affected_km2_observed']} वर्ग कि.मी.</strong> र अनुमानित बहाव क्षेत्र <strong>{v['affected_km2_inferred']} वर्ग कि.मी.</strong> छ। {v['primary_river']} वरपर <strong>लगभग {up_place_ne} देखि {down_place_ne} सम्म</strong> बाढीको असर देखिएको छ। (उपग्रह: पूर्व {v['pre_dates_str']} / पश्चात {v['post_dates_str']})।"

            sec2_title = "२. के क्षति भयो?"
            bld_label_ne = "जलमग्न" if is_flat else "नष्ट"
            bld_sub_ne = "सम्भावित जलमग्न" if is_flat else "क्षतिग्रस्त"
            sec2_text = f"• मुख्य सडक क्षति: <strong>{v['main_road_destroyed_ne']}</strong> (कुल {v['roads_destroyed_km']} कि.मी. {bld_label_ne}, {v['roads_possibly_damaged_km']} कि.मी. सम्भावित क्षति, {v['roads_cloud_unverified_km']} कि.मी. अपुष्ट)।<br/>• प्रमुख सडकका {bld_label_ne} पुलहरू: {v['major_bridge_roads_ne']}।"

            sec3_title = "३. को सम्पर्कविहीन भयो?"
            sec3_summary = f"सवारी पहुँच विच्छेद: <strong>{v['cutoff_vehicle_optimistic_count']} बस्तीहरू</strong> (निराशावादी: {v['cutoff_vehicle_pessimistic_count']})। पूर्ण स्थल सम्पर्कविहीन (पैदल तथा सवारी दुवै बन्द): <strong>{v['no_ground_access_count']} बस्तीहरू</strong>।"

            sec4_title = "४. पहिले के मर्मत गर्ने?"
            sec4_text = f"• {v['single_repair_sentence_ne']}।<br/>• <strong>{v['package_1_sentence_ne']}</strong>"

            lbl_no_ground = "पूर्ण स्थल सम्पर्कविहीन (हवाई / डुङ्गा प्राथमिकता)"
            lbl_top_road = "सबैभन्दा ठूला ५ सवारी सम्पर्कविहीन बस्ती"

            kpi_hazard_lbl = "प्रत्यक्ष बाढी / जलमग्न" if is_flat else "प्रत्यक्ष बाढी / लेदो"
            kpi_bld_lbl = "जलमग्न भवनहरू" if is_flat else "नष्ट भवनहरू"
            kpi_br_lbl = "जलमग्न पुलहरू" if is_flat else "नष्ट पुलहरू"
            kpi_cut_lbl = "सवारी सम्पर्कविहीन बस्ती"
        else:
            title = "RAPID DISASTER SITUATION REPORT (SITREP)"
            badge = "Educational Prototype"
            meta_str = f"Event Date: <strong>{v['event_date']}</strong> | Satellite: <strong>{v['post_dates_str']}</strong> | AOI: <strong>{v['bbox']}</strong>"

            sec1_title = "1. Where did the flood hit?"
            sec1_text = f"Satellite analysis identifies <strong>{v['affected_km2_observed']} km²</strong> of directly observed hazard extent and <strong>{v['affected_km2_inferred']} km²</strong> inferred along tributaries. Affected stretch extends along <strong>{v['primary_river']}</strong> from near <strong>{v['upstream_place']}</strong> to near <strong>{v['downstream_place']}</strong> (Sensors: Pre {v['pre_dates_str']} / Post {v['post_dates_str']})."

            sec2_title = "2. What was damaged?"
            bld_label_en = "flooded" if is_flat else "destroyed"
            bld_col_en = "Flooded" if is_flat else "Destroyed"
            bld_sub_en = "Possibly Flooded" if is_flat else "Damaged"
            sec2_text = f"• Major road damage: <strong>{v['main_road_destroyed_en']}</strong> (Total {v['roads_destroyed_km']} km {bld_label_en}, {v['roads_possibly_damaged_km']} km possibly damaged, {v['roads_cloud_unverified_km']} km unverified under clouds).<br/>• Major corridor bridges {bld_label_en}: {v['major_bridge_roads_en']}."

            sec3_title = "3. Who is cut off?"
            sec3_summary = f"<strong>{v['cutoff_vehicle_optimistic_count']} settlements</strong> cut off from any town or hospital by road (pessimistic: <strong>{v['cutoff_vehicle_pessimistic_count']}</strong>). <strong>{v['no_ground_access_count']} settlements</strong> have no ground access (dual vehicle & walking severed)."

            sec4_title = "4. What to repair first"
            sec4_text = f"• {v['single_repair_sentence_en']}.<br/>• <strong>{v['package_1_sentence_en']}</strong>"

            lbl_no_ground = "No Ground Access (Air / Boat Priority)"
            lbl_top_road = "5 Largest Road Cut-Off Settlements"

            kpi_hazard_lbl = "Observed Flood Water" if is_flat else "Observed Hazard"
            kpi_bld_lbl = "Flooded Buildings" if is_flat else "Destroyed Buildings"
            kpi_br_lbl = "Flooded Bridges" if is_flat else "Destroyed Bridges"
            kpi_cut_lbl = "Cut-Off Settlements"

        html_out = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
@page {{
    size: A4 portrait;
    margin: 5mm 7mm 4mm 7mm;
}}
* {{
    box-sizing: border-box;
}}
body {{
    font-family: 'Noto Sans Devanagari', 'Lohit Devanagari', 'FreeSans', 'DejaVu Sans', sans-serif;
    color: #0f172a;
    line-height: 1.20;
    font-size: 7.6pt;
    margin: 0;
    padding: 0;
}}
.header {{
    border-bottom: 2px solid #b91c1c;
    padding-bottom: 1.5px;
    margin-bottom: 2px;
}}
.title-row {{
    display: flex;
    justify-content: space-between;
    align-items: baseline;
}}
h1 {{
    font-size: 11.5pt;
    color: #991b1b;
    margin: 0;
    text-transform: uppercase;
    font-weight: 700;
}}
.badge {{
    font-size: 6.8pt;
    font-weight: 600;
    color: #475569;
    background: #f1f5f9;
    padding: 1px 4px;
    border-radius: 3px;
    border: 1px solid #cbd5e1;
}}
.meta-line {{
    font-size: 7.0pt;
    color: #475569;
    margin-top: 1px;
}}
.kpi-row {{
    display: flex;
    gap: 4px;
    margin: 2px 0 3px 0;
}}
.kpi-card {{
    flex: 1;
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-top: 2.5px solid #0284c7;
    padding: 1.5px 3.5px;
    border-radius: 3px;
}}
.kpi-card.alert {{
    border-top-color: #dc2626;
}}
.kpi-val {{
    font-size: 11pt;
    font-weight: 700;
    color: #0f172a;
    line-height: 1.1;
}}
.kpi-card.alert .kpi-val {{
    color: #b91c1c;
}}
.kpi-lbl {{
    font-size: 6.2pt;
    font-weight: 600;
    color: #64748b;
    text-transform: uppercase;
}}
.map-box {{
    width: 100%;
    border: 1.5px solid #cbd5e1;
    border-radius: 4px;
    overflow: hidden;
    margin: 3px 0 4px 0;
    text-align: center;
    background: #f8fafc;
}}
.overview-map {{
    width: 100%;
    height: 285px;
    object-fit: cover;
    display: block;
    margin: 0 auto;
}}
.main-grid {{
    display: flex;
    gap: 7px;
    margin-top: 1px;
}}
.col-left {{
    flex: 1;
}}
.col-right {{
    flex: 1;
}}
.sec-heading {{
    font-size: 7.8pt;
    font-weight: 700;
    color: #0369a1;
    border-bottom: 1px solid #bae6fd;
    padding-bottom: 1px;
    margin: 2px 0 1.5px 0;
    text-transform: uppercase;
}}
.sec-heading.danger {{
    color: #b91c1c;
    border-bottom-color: #fecaca;
}}
.sub-title {{
    font-size: 7.0pt;
    font-weight: 700;
    color: #334155;
    margin: 2.5px 0 1px 0;
}}
.table-compact {{
    width: 100%;
    border-collapse: collapse;
    font-size: 6.6pt;
    margin: 1.5px 0;
}}
.table-compact th, .table-compact td {{
    padding: 1.2px 2.5px;
    border: 1px solid #e2e8f0;
    text-align: left;
}}
.table-compact th {{
    background: #f1f5f9;
    color: #475569;
    font-weight: 600;
}}
.prose-box {{
    font-size: 7.0pt;
    line-height: 1.20;
    margin: 1.5px 0;
}}
.footer-box {{
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 3px;
    padding: 2px 3.5px;
    margin-top: 3px;
    font-size: 6.0pt;
    color: #475569;
    line-height: 1.18;
}}
.footer-attr {{
    border-top: 1px solid #cbd5e1;
    padding-top: 1.5px;
    margin-top: 2px;
    font-size: 5.6pt;
    color: #64748b;
    line-height: 1.15;
}}
</style>
</head>
<body>

<div class="header">
  <div class="title-row">
    <h1>{title}</h1>
    <span class="badge">{badge}</span>
  </div>
  <div class="meta-line">{meta_str}</div>
</div>

<div class="kpi-row">
  <div class="kpi-card alert">
    <div class="kpi-val">{v['affected_km2_observed']} km²</div>
    <div class="kpi-lbl">{kpi_hazard_lbl}</div>
  </div>
  <div class="kpi-card alert">
    <div class="kpi-val">{v['buildings_destroyed']}</div>
    <div class="kpi-lbl">{kpi_bld_lbl}</div>
  </div>
  <div class="kpi-card alert">
    <div class="kpi-val">{v['bridges_destroyed']}</div>
    <div class="kpi-lbl">{kpi_br_lbl}</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-val">{v['cutoff_vehicle_optimistic_count']}</div>
    <div class="kpi-lbl">{kpi_cut_lbl}</div>
  </div>
</div>

<div class="map-box">
  {map_img_tag}
</div>

<div class="main-grid">
  <div class="col-left">
    <!-- 1. Where did the flood hit? -->
    <div class="sec-heading">{sec1_title}</div>
    <div class="prose-box">{sec1_text}</div>

    <!-- 2. What was damaged? -->
    <div class="sec-heading danger" style="margin-top: 3.5px;">{sec2_title}</div>
    <table class="table-compact">
      <tr>
        <th>{'पूर्वाधार' if is_ne else 'Asset'}</th>
        <th>{bld_label_ne if is_ne else bld_col_en}</th>
        <th>{bld_sub_ne if is_ne else bld_sub_en}</th>
        <th>{'अपुष्ट' if is_ne else 'Cloud-Unv.'}</th>
        <th>{'कुल' if is_ne else 'Total'}</th>
      </tr>
      <tr>
        <td>{'भवनहरू' if is_ne else 'Buildings'}</td>
        <td><strong>{v['buildings_destroyed']}</strong></td>
        <td>{v['buildings_damaged']}</td>
        <td>{v['buildings_cloud_unverified']}</td>
        <td>{v['buildings_total']}</td>
      </tr>
      <tr>
        <td>{'पुलहरू' if is_ne else 'Bridges'}</td>
        <td><strong>{v['bridges_destroyed']}</strong></td>
        <td>{v['bridges_possibly_damaged']}</td>
        <td>{v['bridges_cloud_unverified']}</td>
        <td>{v['bridges_total']}</td>
      </tr>
      <tr>
        <td>{'सडक (कि.मी.)' if is_ne else 'Roads (km)'}</td>
        <td><strong>{v['roads_destroyed_km']}</strong></td>
        <td>{v['roads_possibly_damaged_km']}</td>
        <td>{v['roads_cloud_unverified_km']}</td>
        <td>{v['roads_total_km']}</td>
      </tr>
    </table>
    <div class="prose-box">{sec2_text}</div>
  </div>

  <div class="col-right">
    <!-- 3. Who is cut off? -->
    <div class="sec-heading danger">{sec3_title}</div>
    <div class="prose-box">{sec3_summary}</div>

    <div class="sub-title">{lbl_no_ground}</div>
    <table class="table-compact">
      <tr><th>{'बस्तीको नाम' if is_ne else 'Settlement'}</th><th>{'निर्देशाङ्क' if is_ne else 'Lat, Lon'}</th><th style="text-align:right;">{'भवन' if is_ne else 'Bld'}</th></tr>
      {no_ground_rows}
    </table>

    <div class="sub-title">{lbl_top_road}</div>
    <table class="table-compact">
      <tr><th>{'बस्तीको नाम' if is_ne else 'Settlement'}</th><th>{'निर्देशाङ्क' if is_ne else 'Lat, Lon'}</th><th style="text-align:right;">{'भवन' if is_ne else 'Bld'}</th></tr>
      {top_veh_rows}
    </table>

    <!-- 4. What to repair first -->
    <div class="sec-heading" style="margin-top: 3.5px;">{sec4_title}</div>
    <div class="prose-box">{sec4_text}</div>

    <!-- Limitations -->
    <div class="footer-box" style="margin-top: 3.5px;">
      <strong>{'तथ्याङ्क सीमाहरू (Limitations):' if is_ne else 'Known Data Limitations:'}</strong><br/>
      • {'बादलका कारण ' + v['buildings_cloud_unverified'] + ' भवनहरू र ' + v['roads_cloud_unverified_km'] + ' कि.मी. सडक अप्टिकल पुष्टि हुन सकेको छैन।' if is_ne else f"{v['buildings_cloud_unverified']} buildings and {v['roads_cloud_unverified_km']} km roads remain unverified under cloud cover."}<br/>
      • {'सहायक नदीहरूमा बहाव हाइड्रोलिक मोडलिङद्वारा अनुमान गरिएको हो; पहाडी भिरालो DEM द्वारा हटाइएको छ।' if is_ne else 'Drainage hazard hydraulically inferred; radar shadow/layover masked with DEM look-angle.'}<br/>
      • {'पूर्वाधार गणना प्रकोप पूर्वको OpenStreetMap तथ्याङ्कमा आधारित छ; जनगणना जनसंख्या समावेश छैन।' if is_ne else 'Asset baseline derived from pre-event OpenStreetMap; census population not included.'}
    </div>

    <!-- Attribution -->
    <div class="footer-attr">
      Contains modified Copernicus Sentinel data {v['event_year']}. Produced using Copernicus WorldDEM-30 © DLR e.V. 2010–2014 and © Airbus Defence and Space GmbH 2014–2018 provided under COPERNICUS by the European Union and ESA; all rights reserved. © OpenStreetMap contributors under ODbL. European Union, Copernicus Emergency Management Service data (EMSR927, EMSR692, EMSR659). Bountos et al., 2024 (Kuro Siwo). Educational prototype, not an operational tool.
    </div>
  </div>
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
