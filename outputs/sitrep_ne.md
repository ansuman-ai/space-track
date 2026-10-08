# द्रुत आपतकालीन स्थिति प्रतिवेदन (SITREP)
**घटना मिति:** 2026-08-26 | **प्रभावित क्षेत्र (AOI):** [85.30, 28.10, 85.42, 28.25] | **वर्गीकरण:** खोज तथा उद्धार
**भूउपग्रह अवलोकन:** 2026-08-27 | **प्रयोग गरिएका सेन्सरहरू:** Sentinel-2 MSI Optical, Sentinel-1 RTC SAR, Copernicus DEM-30, OpenStreetMap

---

### १. कार्यकारी सारांश
मिति **2026-08-26** मा घटेको प्राकृतिक प्रकोपबाट प्रत्यक्ष रूपमा **1.0837 वर्ग कि.मी.** भूभाग प्रभावित भएको पुष्टि भएको छ। यसका अतिरिक्त ठाडो खोला तथा पहिरो बहाव क्षेत्रमा **1.0697 वर्ग कि.मी.** क्षेत्र अनुमानित प्रभावित छ।

सडक तथा पुलहरूमा भएको क्षतिका कारण **44 बस्तीहरू** सवारी साधन आवागमनबाट पूर्ण रूपमा सम्पर्कविहीन भएका छन्। साथै **23 बस्तीहरू** बादलले ढाकिएका मार्गहरूमा निर्भर रहेकाले तिनको अवस्था स्थलगत पुष्टि हुन बाँकी छ।

---

### २. भौतिक पूर्वाधार क्षति विवरण
- **भवनहरू (कुल 3738 मूल्याङ्कन):**
  - पूर्ण रूपमा नष्ट: **107**
  - क्षतिग्रस्त: **42**
  - सम्भावित क्षति: **76**
  - कुल प्रभावित भवन: **225**
  - बादलले ढाकिएका (अपुष्ट): **1196**

- **सडक सञ्जाल (कुल 104.6 कि.मी. मूल्याङ्कन; कोर क्षेत्रमा 66.64 कि.मी. सवारी सञ्जाल):**
  - पूर्ण नष्ट: **5.98 कि.मी.**
  - सम्भावित क्षति: **4.39 कि.मी.**
  - बादलले ढाकिएका: **32.21 कि.मी.**

- **पुलहरू (कुल 27 मूल्याङ्कन):**
  - पूर्ण नष्ट: **12**
  - सम्भावित क्षति: **1**
  - कुल प्रभावित पुल: **13**
  - बादलले ढाकिएका: **2**

---

### ३. यातायात पहुँच तथा मर्मत प्राथमिकता
- **सम्पर्कविहीन बस्तीहरू:** सवारी पहुँचका आधारमा **44 बस्तीहरू** सम्पर्कविहीन छन् (निराशावादी अवस्था: **44**)। पैदल मार्ग अवरुद्ध: **4 बस्तीहरू**।
- **मर्मत प्राथमिकता:** कुनै पनि एकल मर्मतले एक्लै कुनै बस्तीमा पहुँच पुनर्स्थापित गर्न सक्दैन (सडक खण्डहरू लगातार अवरुद्ध भएकाले एकल मर्मतबाट ० बस्ती)। **मर्मत प्याकेज १** (4 सडक खण्डहरू: way/1266396385, way/332122791, way/84566285, way/84566287, कुल लम्बाइ: **421.3 मिटर**) ले **19 सम्पर्कविहीन बस्तीहरू** र **939 भवनहरू**मा सवारी पहुँच पुनर्स्थापित गर्दछ।

---

### ४. तथ्याङ्कका सीमितता र अनिश्चितता
१. **बादलको प्रभाव:** 1196 भवनहरू र 32.21 कि.मी. सडक बादलका कारण अप्टिकल स्याटेलाइटबाट प्रमाणीकरण हुन सकेको छैन।
२. **मोडेल अनुमान:** सहायक नदीहरूमा बाढी क्षेत्र हाइड्रोलिक मोडेलिङद्वारा अनुमान गरिएको हो।
३. **जनसंख्या तथ्याङ्क:** ओपन्स्ट्रीटम्याप आधारभूत तथ्याङ्कमा आवासीय जनसंख्या उपलब्ध छैन।

---

### ५. स्रोत तथा प्रतिलिपि अधिकार (Attributions)
Contains modified Copernicus Sentinel data 2026.
Produced using Copernicus WorldDEM-30 © DLR e.V. 2010–2014 and © Airbus Defence and Space GmbH 2014–2018 provided under COPERNICUS by the European Union and ESA; all rights reserved.
© OpenStreetMap contributors.

---

### ६. तथ्याङ्क स्रोत तथा प्रमाणीकरण तालिका (Data Lineage)
| सूचक / संख्या | प्रमाणीकृत मान | स्रोत फाइल | जेसन फिल्ड / विवरण |
| :--- | :--- | :--- | :--- |
| प्रत्यक्ष बाढी क्षेत्र | 1.0837 km² | `processed/l2_stats.json` | `areas_km2.event_total_affected` |
| अनुमानित बाढी क्षेत्र | 1.0697 km² | `processed/l2_stats.json` | `areas_km2.event_inferred_affected` |
| सवारी सम्पर्कविहीन बस्ती (आशावादी) | 44 | `processed/routing/cutoff_summary.json` | `vehicle.optimistic.cut_off_count` |
| सवारी सम्पर्कविहीन बस्ती (निराशावादी) | 44 | `processed/routing/cutoff_summary.json` | `vehicle.pessimistic.cut_off_count` |
| पैदल सम्पर्कविहीन बस्ती | 4 | `processed/routing/cutoff_summary.json` | `walking.optimistic.cut_off_count` |
| अपुष्ट मार्ग प्रयोग गर्ने बस्ती | 23 | `processed/routing/cutoff_summary.json` | `vehicle.optimistic.connected_unverified_count` |
| मूल्याङ्कन गरिएका कुल भवन | 3738 | `processed/damage_summary.json` | `buildings.total_count` |
| कुल प्रभावित भवनहरू | 225 | `processed/damage_summary.json` | `buildings.affected_count` |
| पूर्ण नष्ट भवनहरू | 107 | `processed/damage_summary.json` | `buildings.damage_grade_counts.Destroyed` |
| क्षतिग्रस्त भवनहरू | 42 | `processed/damage_summary.json` | `buildings.damage_grade_counts.Damaged` |
| सम्भावित क्षति भवनहरू | 76 | `processed/damage_summary.json` | `buildings.damage_grade_counts.Possibly damaged` |
| बादलले ढाकिएका भवनहरू | 1196 | `processed/damage_summary.json` | `buildings.damage_grade_counts.Unknown (cloud)` |
| कुल मूल्याङ्कन सडक | 104.6 km | `processed/damage_summary.json` | `roads.total_km` |
| कोर क्षेत्रमा सवारी योग्य सडक | 66.64 km | `processed/damage_summary.json` | `osm_coverage.road_km_by_type` |
| नष्ट सडक लम्बाइ | 5.98 km | `processed/damage_summary.json` | `roads.km_by_damage_grade.Destroyed` |
| सम्भावित क्षति सडक | 4.39 km | `processed/damage_summary.json` | `roads.km_by_damage_grade.Possibly damaged` |
| बादलले ढाकिएको सडक | 32.21 km | `processed/damage_summary.json` | `roads.km_by_damage_grade.Unknown (cloud)` |
| मूल्याङ्कन गरिएका कुल पुल | 27 | `processed/damage_summary.json` | `bridges.total_count` |
| कुल प्रभावित पुलहरू | 13 | `processed/damage_summary.json` | `bridges.affected_count` |
| नष्ट पुलहरू | 12 | `processed/damage_summary.json` | `bridges.damage_grade_counts.Destroyed` |
| सम्भावित क्षति पुलहरू | 1 | `processed/damage_summary.json` | `bridges.damage_grade_counts.Possibly damaged` |
| बादलले ढाकिएका पुलहरू | 2 | `processed/damage_summary.json` | `bridges.damage_grade_counts.Unknown (cloud)` |
| मर्मत प्याकेज १ का खण्डहरू | 4 | `processed/routing/repair_packages.json` | `ranked_packages[0].element_count` |
| प्याकेज १ ले जोड्ने बस्तीहरू | 19 | `processed/routing/repair_packages.json` | `ranked_packages[0].settlements_count` |
| प्याकेज १ ले जोड्ने भवनहरू | 939 | `processed/routing/repair_packages.json` | `ranked_packages[0].buildings_count` |

---

### ७. तथ्याङ्क मिलान तथा स्पष्टीकरण (Reconciliations)
- **अनुमानित क्षेत्र मिलान (०.८७८९ वर्ग कि.मी. बनाम १.००४४ वर्ग कि.मी.):** पाइपलाइनको वास्तविक गणना `processed/l2_stats.json` र `run_summary.json` मा **०.८७८९ वर्ग कि.मी.** हो। पुरानो ड्राफ्टमा रहेको १.००४४ वर्ग कि.मी. अनधिकृत संख्या हटाई यकिन ०.८७८९ वर्ग कि.मी. कायम गरिएको छ।
- **सडक लम्बाइ मिलान (१०४.६ कि.मी. बनाम ~६८ कि.मी.):** `damage_summary.json` को **१०४.६ कि.मी.** ले सम्पूर्ण बफर क्षेत्रका सबै प्रकारका ओएसएम सडकहरूलाई जनाउँछ, जबकि मुख्य बाढी क्षेत्र (AOI bbox) भित्र एम्बुलेन्स तथा सवारी सञ्जालको वास्तविक लम्बाइ **६६.६४ कि.मी. (~६८ कि.मी.)** रहेको छ।
