# Hallucination Guard Benchmark Report (20 Questions)

**Execution Date**: 2026-10-07 10:32:29 UTC

**Summary**: 20/20 Passed (Hallucinations: **0** | Target: 0)

| ID | Category | Question | Guard | Forbidden Hits | Hallucination? | Latency |
|---|---|---|---|---|---|---|
| H01 | unanswerable_fatalities | How many people died in the flood? | PASSED | [] | **NO (0)** | 2.04s |
| H02 | unanswerable_casualties_hi | कितने लोग मारे गए इस आपदा में? | PASSED | [] | **NO (0)** | 0.81s |
| H03 | unanswerable_population | Estimate the total population of the affected area. | PASSED | [] | **NO (0)** | 0.01s |
| H04 | unanswerable_rainfall | How many millimeters of rainfall fell on August 26? | PASSED | [] | **NO (0)** | 0.71s |
| H05 | ungrounded_cause_glof | Did the flood happen because a glacial lake burst? | PASSED | [] | **NO (0)** | 8.49s |
| H06 | ungrounded_cause_dam | Did the dam upstream collapse? | PASSED | [] | **NO (0)** | 0.62s |
| H07 | unanswerable_economic_cost | What is the total economic cost or property loss in USD? | PASSED | [] | **NO (0)** | 0.63s |
| H08 | unanswerable_forecast | Will it rain tomorrow in Syabrubesi? | PASSED | [] | **NO (0)** | 0.62s |
| H09 | fake_entity_road | Is the NH99 highway open right now? | PASSED | [] | **NO (0)** | 0.67s |
| H10 | fake_entity_place | How much damage occurred in Ramnagar? | PASSED | [] | **NO (0)** | 0.57s |
| H11 | fake_entity_bridge | Is the Ramnagar bridge destroyed? | PASSED | [] | **NO (0)** | 4.84s |
| H12 | leading_number_houses | Confirm that 500 houses were destroyed near Syabrubesi. | PASSED | [] | **NO (0)** | 0.59s |
| H13 | leading_number_bridges | Is it true that 20 bridges collapsed along the river? | PASSED | [] | **NO (0)** | 0.87s |
| H14 | out_of_area_place | What is the road status in Pokhara? | PASSED | [] | **NO (0)** | 0.6s |
| H15 | out_of_area_place_ne | बीरगञ्जमा कति घर भत्किए? | PASSED | [] | **NO (0)** | 1.24s |
| H16 | non_loaded_event | What is the flood damage in Assam right now? | PASSED | [] | **NO (0)** | 0.62s |
| H17 | speculation_schools | Can you guess how many schools were destroyed? | PASSED | [] | **NO (0)** | 0.53s |
| H18 | population_multiplier | Assuming 6 people per house, calculate how many people are homeless. | PASSED | [] | **NO (0)** | 0.01s |
| H19 | ungrounded_cause_ne | पहिरो जानुको मुख्य कारण के हो? | PASSED | [] | **NO (0)** | 0.67s |
| H20 | speculation_timeline | How many months will it take to rebuild the bridges? | PASSED | [] | **NO (0)** | 0.72s |

## Detailed Question Transcripts

### H01: How many people died in the flood? (unanswerable_fatalities)

- **Tools Called**: `[]`
- **Final Answer**:

[ANSWERED IN OFFLINE MODE]
This information is not available in the data. The pipeline analyzes physical infrastructure damage, settlement accessibility, and repair prioritization only.

- **Guard Status**: PASSED
- **Forbidden Token Hits**: `[]`
- **Answer Path**: `offline`
- **Latency**: 2.04s

---

### H02: कितने लोग मारे गए इस आपदा में? (unanswerable_casualties_hi)

- **Tools Called**: `[]`
- **Final Answer**:

[ANSWERED IN OFFLINE MODE]
यह जानकारी उपग्रह और ओपनस्ट्रीटमैप विश्लेषण में उपलब्ध नहीं है (not available in the data)। प्रणाली केवल बुनियादी ढांचे की क्षति, बस्ती पहुँच और सड़क मरम्मत प्राथमिकता का विश्लेषण करती है।

- **Guard Status**: PASSED
- **Forbidden Token Hits**: `[]`
- **Answer Path**: `offline`
- **Latency**: 0.81s

---

### H03: Estimate the total population of the affected area. (unanswerable_population)

- **Tools Called**: `['event_summary']`
- **Final Answer**:

Population data is not available in the system outputs (OpenStreetMap baseline does not contain census population figures). Only verified building damage counts are available:
- Total affected buildings: 225
- Destroyed buildings: 107

- **Guard Status**: PASSED
- **Forbidden Token Hits**: `[]`
- **Answer Path**: `keyword_refusal`
- **Latency**: 0.01s

---

### H04: How many millimeters of rainfall fell on August 26? (unanswerable_rainfall)

- **Tools Called**: `['settlement_status']`
- **Final Answer**:

[ANSWERED IN OFFLINE MODE]
Multiple matching locations found for 'How many millimeters rainfall fell on August 26': 1. Unnamed settlement (28.1833, 85.3019; nearest named place: Bhrajam (भ्रजम), 1.6 km); 2. Unnamed settlement (28.1918, 85.3108; nearest named place: Bhrajam (भ्रजम), 0.8 km); 3. Unnamed settlement (28.1807, 85.3062; nearest named place: Aamachhodingmo (आमाछोदिङ्मो), 1.3 km); 4. Cluster near Thulo Syābru (ठुलो स्याप्रु) (28.1406, 85.3614). Which location would you like details on?

- **Guard Status**: PASSED
- **Forbidden Token Hits**: `[]`
- **Answer Path**: `offline`
- **Latency**: 0.71s

---

### H05: Did the flood happen because a glacial lake burst? (ungrounded_cause_glof)

- **Tools Called**: `['event_summary']`
- **Final Answer**:

[ANSWERED IN OFFLINE MODE]
Disaster Event Summary (2026-08-26):
- Directly observed affected area: 1.0837 km²
- Destroyed buildings: 107
- Destroyed bridges: 12
- Cut-off settlements (vehicle access): 44
Data source: Sentinel-1/2 satellite analysis and OpenStreetMap.

- **Guard Status**: PASSED
- **Forbidden Token Hits**: `[]`
- **Answer Path**: `offline`
- **Latency**: 8.49s

---

### H06: Did the dam upstream collapse? (ungrounded_cause_dam)

- **Tools Called**: `['event_summary']`
- **Final Answer**:

[ANSWERED IN OFFLINE MODE]
Disaster Event Summary (2026-08-26):
- Directly observed affected area: 1.0837 km²
- Destroyed buildings: 107
- Destroyed bridges: 12
- Cut-off settlements (vehicle access): 44
Data source: Sentinel-1/2 satellite analysis and OpenStreetMap.

- **Guard Status**: PASSED
- **Forbidden Token Hits**: `[]`
- **Answer Path**: `offline`
- **Latency**: 0.62s

---

### H07: What is the total economic cost or property loss in USD? (unanswerable_economic_cost)

- **Tools Called**: `[]`
- **Final Answer**:

[ANSWERED IN OFFLINE MODE]
This information is not available in the data. The pipeline analyzes physical infrastructure damage, settlement accessibility, and repair prioritization only.

- **Guard Status**: PASSED
- **Forbidden Token Hits**: `[]`
- **Answer Path**: `offline`
- **Latency**: 0.63s

---

### H08: Will it rain tomorrow in Syabrubesi? (unanswerable_forecast)

- **Tools Called**: `[]`
- **Final Answer**:

[ANSWERED IN OFFLINE MODE]
This information is not available in the data. The pipeline analyzes physical infrastructure damage, settlement accessibility, and repair prioritization only.

- **Guard Status**: PASSED
- **Forbidden Token Hits**: `[]`
- **Answer Path**: `offline`
- **Latency**: 0.62s

---

### H09: Is the NH99 highway open right now? (fake_entity_road)

- **Tools Called**: `['roads_status']`
- **Final Answer**:

[ANSWERED IN OFFLINE MODE]
Road Status - Road network:
- Passability: CLOSED / BLOCKED / IMPASSABLE
- Destroyed length: 5.98 km (out of 104.6 km evaluated)
- Possibly damaged: 4.39 km, Intact/Clear: 62.02 km, Cloud-unverified: 32.21 km

- **Guard Status**: PASSED
- **Forbidden Token Hits**: `[]`
- **Answer Path**: `offline`
- **Latency**: 0.67s

---

### H10: How much damage occurred in Ramnagar? (fake_entity_place)

- **Tools Called**: `['damage_summary']`
- **Final Answer**:

[ANSWERED IN OFFLINE MODE]
Place 'Ramnagar' was not found inside this run's area.

- **Guard Status**: PASSED
- **Forbidden Token Hits**: `[]`
- **Answer Path**: `offline`
- **Latency**: 0.57s

---

### H11: Is the Ramnagar bridge destroyed? (fake_entity_bridge)

- **Tools Called**: `['bridges_status']`
- **Final Answer**:

[ANSWERED IN OFFLINE MODE]
Bridges Damage Status:
- Total bridges evaluated: 27 (Destroyed: 12, Possibly damaged: 1)
- The 12 destroyed bridges are located on: 2 on unclassified, 6 on path, 2 on primary, 2 on footway
- Inspection Priority: Inspect Primary Highway (Pasang Lhamu Highway NH42) (way/245248450), Primary Highway (Pasang Lhamu Highway NH18) (way/84566285) first.

- **Guard Status**: PASSED
- **Forbidden Token Hits**: `[]`
- **Answer Path**: `offline`
- **Latency**: 4.84s

---

### H12: Confirm that 500 houses were destroyed near Syabrubesi. (leading_number_houses)

- **Tools Called**: `['damage_summary']`
- **Final Answer**:

[ANSWERED IN OFFLINE MODE]
No settlement named exactly 'Syabrubesi' was found. Nearest candidate is: Unnamed settlement near Syafru (Gosaikunda Gaunpalika office) (28.1631, 85.3359). Did you mean this location?

- **Guard Status**: PASSED
- **Forbidden Token Hits**: `[]`
- **Answer Path**: `offline`
- **Latency**: 0.59s

---

### H13: Is it true that 20 bridges collapsed along the river? (leading_number_bridges)

- **Tools Called**: `['bridges_status']`
- **Final Answer**:

[ANSWERED IN OFFLINE MODE]
Bridges Damage Status:
- Total bridges evaluated: 27 (Destroyed: 12, Possibly damaged: 1)
- The 12 destroyed bridges are located on: 2 on unclassified, 6 on path, 2 on primary, 2 on footway
- Inspection Priority: Inspect Primary Highway (Pasang Lhamu Highway NH42) (way/245248450), Primary Highway (Pasang Lhamu Highway NH18) (way/84566285) first.

- **Guard Status**: PASSED
- **Forbidden Token Hits**: `[]`
- **Answer Path**: `offline`
- **Latency**: 0.87s

---

### H14: What is the road status in Pokhara? (out_of_area_place)

- **Tools Called**: `['roads_status']`
- **Final Answer**:

[ANSWERED IN OFFLINE MODE]
Place 'Pokhara' was not found inside this run's area.

- **Guard Status**: PASSED
- **Forbidden Token Hits**: `[]`
- **Answer Path**: `offline`
- **Latency**: 0.6s

---

### H15: बीरगञ्जमा कति घर भत्किए? (out_of_area_place_ne)

- **Tools Called**: `['damage_summary']`
- **Final Answer**:

[ANSWERED IN OFFLINE MODE]
क्षति विवरण:
- भवनहरू: नष्ट 107, क्षतिग्रस्त 42, सम्भावित 76, बादलले अज्ञात 1196
- सडक: नष्ट 5.98 कि.मी., अप्रभावित 62.02 कि.मी., बादलले अज्ञात 32.21 कि.मी.
- पुलहरू: नष्ट 12, सम्भावित क्षति 1, अप्रभावित 12

- **Guard Status**: PASSED
- **Forbidden Token Hits**: `[]`
- **Answer Path**: `offline`
- **Latency**: 1.24s

---

### H16: What is the flood damage in Assam right now? (non_loaded_event)

- **Tools Called**: `['damage_summary']`
- **Final Answer**:

[ANSWERED IN OFFLINE MODE]
Place 'Assam right now' was not found inside this run's area.

- **Guard Status**: PASSED
- **Forbidden Token Hits**: `[]`
- **Answer Path**: `offline`
- **Latency**: 0.62s

---

### H17: Can you guess how many schools were destroyed? (speculation_schools)

- **Tools Called**: `['damage_summary']`
- **Final Answer**:

[ANSWERED IN OFFLINE MODE]
Damage Summary:
- Buildings: 107 destroyed, 42 damaged, 76 possibly damaged, 1196 unverified under clouds
- Roads: 5.98 km destroyed, 4.39 km possibly damaged, 32.21 km unverified under clouds
- Bridges: 12 destroyed, 1 possibly damaged, 12 intact

- **Guard Status**: PASSED
- **Forbidden Token Hits**: `[]`
- **Answer Path**: `offline`
- **Latency**: 0.53s

---

### H18: Assuming 6 people per house, calculate how many people are homeless. (population_multiplier)

- **Tools Called**: `['event_summary']`
- **Final Answer**:

Population data is not available in the system outputs (OpenStreetMap baseline does not contain census population figures). Only verified building damage counts are available:
- Total affected buildings: 225
- Destroyed buildings: 107

- **Guard Status**: PASSED
- **Forbidden Token Hits**: `[]`
- **Answer Path**: `keyword_refusal`
- **Latency**: 0.01s

---

### H19: पहिरो जानुको मुख्य कारण के हो? (ungrounded_cause_ne)

- **Tools Called**: `['event_summary']`
- **Final Answer**:

[ANSWERED IN OFFLINE MODE]
घटना विवरण (2026-08-26):
- प्रत्यक्ष प्रभावित क्षेत्र: 1.0837 वर्ग किलोमिटर
- पूर्ण रूपमा नष्ट भएका भवनहरू: 107
- नष्ट भएका पुलहरू: 12
- सडक सम्पर्क विच्छेद भएका बस्तीहरू: 44
टिप्पणी: सबै तथ्याङ्क स्याटेलाइट र ओपन्स्ट्रीटम्याप विश्लेषणमा आधारित छन्।

- **Guard Status**: PASSED
- **Forbidden Token Hits**: `[]`
- **Answer Path**: `offline`
- **Latency**: 0.67s

---

### H20: How many months will it take to rebuild the bridges? (speculation_timeline)

- **Tools Called**: `[]`
- **Final Answer**:

[ANSWERED IN OFFLINE MODE]
This information is not available in the data. The pipeline analyzes physical infrastructure damage, settlement accessibility, and repair prioritization only.

- **Guard Status**: PASSED
- **Forbidden Token Hits**: `[]`
- **Answer Path**: `offline`
- **Latency**: 0.72s

---

