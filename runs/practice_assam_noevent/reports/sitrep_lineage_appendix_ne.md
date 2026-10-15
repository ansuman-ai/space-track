# स्थिति प्रतिवेदन — अनुसूची: तथ्याङ्क स्रोत तथा प्रमाणीकरण तालिका
**घटना मिति:** 2024-01-15 | **प्रभावित क्षेत्र (AOI):** [92.85, 26.55, 93.10, 26.75] | **विश्लेषण निर्देशिका:** `/home/zeus/Downloads/project1/runs/practice_assam_noevent`

यस अनुसूचीले १-पृष्ठको स्थिति प्रतिवेदनमा उल्लिखित प्रत्येक तथ्याङ्कलाई पाइपलाइनको आधिकारिक JSON फाइलसँग सिधै जोड्दछ।

| सूचक / विवरण | प्रमाणीकृत मान | स्रोत फाइल | जेसन फिल्ड / विवरण |
| :--- | :--- | :--- | :--- |
| प्रत्यक्ष बाढी / लेदो क्षेत्र | 0.05 km² | `processed/l2_stats.json` | `areas_km2.event_total_affected` |
| अनुमानित बाढी क्षेत्र | 0.0 km² | `processed/l2_stats.json` | `areas_km2.event_inferred_affected` |
| सवारी सम्पर्कविहीन बस्ती (आशावादी) | 0 | `processed/routing/cutoff_summary.json` | `vehicle.optimistic.cut_off_count` |
| सवारी सम्पर्कविहीन बस्ती (निराशावादी) | 0 | `processed/routing/cutoff_summary.json` | `vehicle.pessimistic.cut_off_count` |
| पैदल सम्पर्कविहीन बस्ती | 0 | `processed/routing/cutoff_summary.json` | `walking.optimistic.cut_off_count` |
| पूर्ण स्थल सम्पर्कविहीन बस्ती | 0 | `processed/routing/settlements.geojson` | `vehicle_status_opt == 'cut_off' and walking_status_opt == 'cut_off'` |
| मूल्याङ्कन गरिएका कुल भवन | 2191 | `processed/damage_summary.json` | `buildings.total_count` |
| कुल प्रभावित भवनहरू | 0 | `processed/damage_summary.json` | `buildings.affected_count` |
| नष्ट / जलमग्न भवनहरू | 0 | `processed/damage_summary.json` | `buildings.damage_grade_counts` |
| क्षतिग्रस्त भवनहरू | 0 | `processed/damage_summary.json` | `buildings.damage_grade_counts` |
| सम्भावित क्षति भवनहरू | 0 | `processed/damage_summary.json` | `buildings.damage_grade_counts` |
| बादलले ढाकिएका भवनहरू | 0 | `processed/damage_summary.json` | `buildings.damage_grade_counts.Unknown (cloud)` |
| कुल मूल्याङ्कन सडक लम्बाइ | 381.43 km | `processed/damage_summary.json` | `roads.total_km` |
| कोर क्षेत्रमा सवारी योग्य सडक | 214.7 km | `processed/damage_summary.json` | `osm_coverage.road_km_by_type` |
| नष्ट सडक लम्बाइ | 0.0 km | `processed/damage_summary.json` | `roads.km_by_damage_grade.Destroyed` |
| सम्भावित क्षति सडक | 0.0 km | `processed/damage_summary.json` | `roads.km_by_damage_grade.Possibly damaged` |
| बादलले ढाकिएको सडक | 0.0 km | `processed/damage_summary.json` | `roads.km_by_damage_grade.Unknown (cloud)` |
| मूल्याङ्कन गरिएका कुल पुल | 22 | `processed/damage_summary.json` | `bridges.total_count` |
| कुल प्रभावित पुलहरू | 0 | `processed/damage_summary.json` | `bridges.affected_count` |
| नष्ट / जलमग्न पुलहरू | 0 | `processed/damage_summary.json` | `bridges.damage_grade_counts` |
| सम्भावित क्षति पुलहरू | 0 | `processed/damage_summary.json` | `bridges.damage_grade_counts` |
| बादलले ढाकिएका पुलहरू | 0 | `processed/damage_summary.json` | `bridges.damage_grade_counts.Unknown (cloud)` |
| मर्मत प्याकेज १ का खण्डहरू | 0 | `processed/routing/repair_packages.json` | `ranked_packages[0].element_count` |
| प्याकेज १ ले जोड्ने बस्तीहरू | 0 | `processed/routing/repair_packages.json` | `ranked_packages[0].settlements_count` |
| प्याकेज १ ले जोड्ने भवनहरू | 0 | `processed/routing/repair_packages.json` | `ranked_packages[0].buildings_count` |

---
**प्रतिलिपि अधिकार तथा स्रोत:**
Contains modified Copernicus Sentinel data 2024.
Produced using Copernicus WorldDEM-30 © DLR e.V. 2010–2014 and © Airbus Defence and Space GmbH 2014–2018 provided under COPERNICUS by the European Union and ESA; all rights reserved.
© OpenStreetMap contributors under ODbL.
European Union, Copernicus Emergency Management Service data (EMSR927, EMSR692, EMSR659).
Bountos et al., 2024 (Kuro Siwo).
Educational prototype, not an operational tool.
