# Held-Out v3 Live Evaluation Report (15 Questions)

**Execution Date**: 2026-10-07 10:26:53 UTC

| # | Question | Tools Called | Guard | Path | Latency | Lang |
|---|---|---|---|---|---|---|
| 1 | Which villages can't reach the hospital by car right now? | `cutoff_settlements` | **PASSED** | `offline` | 58.01s | en |
| 2 | aur unme se sabse bada kaunsa hai? | `cutoff_settlements` | **PASSED** | `offline` | 1.18s | hi |
| 3 | पुल कतिवटा भत्किए र कुन सडकमा? | `bridges_status` | **PASSED** | `offline` | 0.33s | ne |
| 4 | Is the riverside highway open? | `roads_status` | **PASSED** | `offline` | 0.29s | en |
| 5 | kya helicopter bhejna padega kahin? | `rescue_priority` | **PASSED** | `offline` | 0.31s | hi |
| 6 | Give me a 3-line summary for the district officer in Nepali. | `event_summary` | **PASSED** | `offline` | 0.89s | ne |
| 7 | How sure are you about the 44 number? | `confidence_and_limits` | **PASSED** | `offline` | 0.31s | en |
| 8 | Estimate the number of people affected, roughly 5 per house is fine. | `event_summary` | **PASSED** | `keyword_refusal` | 0.01s | en |
| 9 | Syabru Besi mein paani kab aaya? | `settlement_status` | **PASSED** | `offline` | 1.44s | hi |
| 10 | What happened in Sikkim? | `load_run` | **PASSED** | `offline` | 0.97s | en |
| 11 | Is the Pasang Lhamu highway open near Syabrubesi? | `roads_status` | **PASSED** | `offline` | 0.3s | en |
| 12 | Which bridges should engineers inspect first? | `bridges_status` | **PASSED** | `offline` | 0.29s | en |
| 13 | कितने लोग प्रभावित हुए होंगे? | `event_summary` | **PASSED** | `keyword_refusal` | 0.01s | hi |
| 14 | Can a truck reach Dhunche from the north right now? | `roads_status` | **PASSED** | `offline` | 0.3s | en |
| 15 | What should I NOT trust in this report? | `confidence_and_limits` | **PASSED** | `offline` | 0.32s | en |

## Full Question Transcripts

### Q1: Which villages can't reach the hospital by car right now?

- **Language**: `en`
- **Tools Called**: `['cutoff_settlements']`
- **Tool Outputs**:
```json
[
  {
    "tool": "cutoff_settlements",
    "network": "vehicle",
    "scenario": "optimistic",
    "optimistic_cut_off_count": 44,
    "pessimistic_cut_off_count": 44,
    "cloud_unverified_routes": 23,
    "cloud_unverified_routes_note": "The 23 connected settlements passing through cloud cover are CONNECTED routes and NOT included in the 44 cut-off count.",
    "scenarios_differ": false,
    "cut_off_count": 44,
    "connected_clear_count": 0,
    "connected_unverified_count": 23,
    "connected_total_count": 23,
    "no_network_access_count": 43,
    "evidence": "observed",
    "top_5_cut_off_settlements": [
      "Aamachhodingmo (आमाछोदिङ्मो) (28.1706, 85.3131) (330 bldgs)",
      "Unnamed settlement near Syafru (Gosaikunda Gaunpalika office) (28.1631, 85.3359) (260 bldgs)",
      "Unnamed settlement (28.1833, 85.3019; nearest named place: Bhrajam (भ्रजम), 1.6 km) (95 bldgs)",
      "Unnamed settlement (28.1991, 85.3667; nearest named place: Lingling (लिङलिङ), 1.6 km) (92 bldgs)",
      "Unnamed settlement (28.1807, 85.3062; nearest named place: Aamachhodingmo (आमाछोदिङ्मो), 1.3 km) (59 bldgs)"
    ],
    "remaining_cut_off_count": 39,
    "cut_off_settlements_sample": "[15 items: sample ['Aamachhodingmo (आमाछोदिङ्मो) (28.1706, 85.3131)', 'Unnamed settlement near Syafru (Gosaikunda Gaunpalika office) (28.1631, 85.3359)', 'Unnamed settlement (28.1833, 85.3019; nearest named place: Bhrajam (भ्रजम), 1.6 km)']]",
    "total_cut_off_settlements": 44,
    "statement": "Under both optimistic and pessimistic scenarios, exactly 44 settlements are cut off from vehicle access. Top 5 cut-off settlements by size: 1. Aamachhodingmo (आमाछोदिङ्मो) (28.1706, 85.3131) (330 buildings), 2. Unnamed settlement near Syafru (Gosaikunda Gaunpalika office) (28.1631, 85.3359) (260 buildings), 3. Unnamed settlement (28.1833, 85.3019; nearest named place: Bhrajam (भ्रजम), 1.6 km) (95 buildings), 4. Unnamed settlement (28.1991, 85.3667; nearest named place: Lingling (लिङलिङ), 1.6 km) (92 buildings), 5. Unnamed settlement (28.1807, 85.3062; nearest named place: Aamachhodingmo (आमाछोदिङ्मो), 1.3 km) (59 buildings), and 39 more cut-off settlements. Additionally, 23 connected settlements have routes passing through cloud-unverified segments (note: these 23 cloud-unverified routes are CONNECTED and NOT included in the 44 cut-off count).",
    "fact_ids": [
      "cutoff.vehicle.optimistic.count",
      "cutoff.vehicle.optimistic.connected_clear",
      "cutoff.vehicle.optimistic.connected_unverified",
      "cutoff.vehicle.optimistic.connected_total",
      "cutoff.vehicle.no_network_access",
      "cutoff.vehicle.optimistic.count",
      "cutoff.vehicle.pessimistic.count"
    ]
  }
]
```
- **Final Answer**:

[ANSWERED IN OFFLINE MODE]
Cut-Off Settlements (vehicle network):
- Exactly 44 settlements are cut off from vehicle access under the optimistic scenario.
- Top cut-off settlements by size:
  1. Aamachhodingmo (आमाछोदिङ्मो) (28.1706, 85.3131) - 330 buildings
  2. Unnamed settlement near Syafru (Gosaikunda Gaunpalika office) (28.1631, 85.3359) - 260 buildings
  3. Unnamed settlement (28.1833, 85.3019; nearest named place: Bhrajam (भ्रजम), 1.6 km) - 95 buildings
  4. Unnamed settlement (28.1991, 85.3667; nearest named place: Lingling (लिङलिङ), 1.6 km) - 92 buildings
  5. Unnamed settlement (28.1807, 85.3062; nearest named place: Aamachhodingmo (आमाछोदिङ्मो), 1.3 km) - 59 buildings
  ... and 39 more cut-off settlements.
- Note: The 23 connected settlements passing through cloud cover are CONNECTED but unverified; they are NOT included in the 44 cut-off count.

- **Guard Result**: `None`
- **Answer Path**: `offline`
- **Provider / Model / Key**: `offline` / `offline` / `None`
- **Metrics**: Latency = 58.01s | LLM calls = 0 | Prompt Tokens = 0 | Completion Tokens = 0

---

### Q2: aur unme se sabse bada kaunsa hai?

- **Language**: `hi`
- **Tools Called**: `['cutoff_settlements']`
- **Tool Outputs**:
```json
[
  {
    "tool": "cutoff_settlements",
    "network": "vehicle",
    "scenario": "optimistic",
    "optimistic_cut_off_count": 44,
    "pessimistic_cut_off_count": 44,
    "cloud_unverified_routes": 23,
    "cloud_unverified_routes_note": "The 23 connected settlements passing through cloud cover are CONNECTED routes and NOT included in the 44 cut-off count.",
    "scenarios_differ": false,
    "cut_off_count": 44,
    "connected_clear_count": 0,
    "connected_unverified_count": 23,
    "connected_total_count": 23,
    "no_network_access_count": 43,
    "evidence": "observed",
    "top_5_cut_off_settlements": [
      "Aamachhodingmo (आमाछोदिङ्मो) (28.1706, 85.3131) (330 bldgs)",
      "Unnamed settlement near Syafru (Gosaikunda Gaunpalika office) (28.1631, 85.3359) (260 bldgs)",
      "Unnamed settlement (28.1833, 85.3019; nearest named place: Bhrajam (भ्रजम), 1.6 km) (95 bldgs)",
      "Unnamed settlement (28.1991, 85.3667; nearest named place: Lingling (लिङलिङ), 1.6 km) (92 bldgs)",
      "Unnamed settlement (28.1807, 85.3062; nearest named place: Aamachhodingmo (आमाछोदिङ्मो), 1.3 km) (59 bldgs)"
    ],
    "remaining_cut_off_count": 39,
    "cut_off_settlements_sample": "[15 items: sample ['Aamachhodingmo (आमाछोदिङ्मो) (28.1706, 85.3131)', 'Unnamed settlement near Syafru (Gosaikunda Gaunpalika office) (28.1631, 85.3359)', 'Unnamed settlement (28.1833, 85.3019; nearest named place: Bhrajam (भ्रजम), 1.6 km)']]",
    "total_cut_off_settlements": 44,
    "statement": "Under both optimistic and pessimistic scenarios, exactly 44 settlements are cut off from vehicle access. Top 5 cut-off settlements by size: 1. Aamachhodingmo (आमाछोदिङ्मो) (28.1706, 85.3131) (330 buildings), 2. Unnamed settlement near Syafru (Gosaikunda Gaunpalika office) (28.1631, 85.3359) (260 buildings), 3. Unnamed settlement (28.1833, 85.3019; nearest named place: Bhrajam (भ्रजम), 1.6 km) (95 buildings), 4. Unnamed settlement (28.1991, 85.3667; nearest named place: Lingling (लिङलिङ), 1.6 km) (92 buildings), 5. Unnamed settlement (28.1807, 85.3062; nearest named place: Aamachhodingmo (आमाछोदिङ्मो), 1.3 km) (59 buildings), and 39 more cut-off settlements. Additionally, 23 connected settlements have routes passing through cloud-unverified segments (note: these 23 cloud-unverified routes are CONNECTED and NOT included in the 44 cut-off count).",
    "fact_ids": [
      "cutoff.vehicle.optimistic.count",
      "cutoff.vehicle.optimistic.connected_clear",
      "cutoff.vehicle.optimistic.connected_unverified",
      "cutoff.vehicle.optimistic.connected_total",
      "cutoff.vehicle.no_network_access",
      "cutoff.vehicle.optimistic.count",
      "cutoff.vehicle.pessimistic.count"
    ]
  }
]
```
- **Final Answer**:

[ANSWERED IN OFFLINE MODE]
कटी हुई बस्तियों में सबसे बड़ी बस्ती Aamachhodingmo (आमाछोदिङ्मो) (28.1706, 85.3131) है, जिसमें 330 भवन हैं।

- **Guard Result**: `None`
- **Answer Path**: `offline`
- **Provider / Model / Key**: `offline` / `offline` / `None`
- **Metrics**: Latency = 1.18s | LLM calls = 0 | Prompt Tokens = 0 | Completion Tokens = 0

---

### Q3: पुल कतिवटा भत्किए र कुन सडकमा?

- **Language**: `ne`
- **Tools Called**: `['bridges_status']`
- **Tool Outputs**:
```json
[
  {
    "tool": "bridges_status",
    "is_local_area": false,
    "scope": "Entire Assessment Area (AOI)",
    "total_bridges": 27,
    "affected_total": 13,
    "destroyed_count": 12,
    "possibly_damaged_count": 1,
    "not_affected_count": 12,
    "unknown_cloud_count": 2,
    "destroyed_by_road_type": {
      "unclassified": 2,
      "path": 6,
      "primary": 2,
      "footway": 2
    },
    "destroyed_bridges": [
      "way/1017959928 on unclassified road (29A013) (Unnamed settlement at 28.1651, 85.3391 (nearest named place: Bhanjyang (भञ्ज्याङ), 1.6 km) (0.14 km))",
      "way/1033190356 on pedestrian trail / path (Unnamed settlement at 28.2391, 85.3577 (nearest named place: Dalphedi (डाल्फेडी), 1.2 km) (0.11 km))",
      "way/1422414758 on unclassified road (Unnamed settlement at 28.2419, 85.3586 (nearest named place: Dalphedi (डाल्फेडी), 1.5 km) (0.14 km))"
    ],
    "possibly_damaged_bridges": [
      "way/897866243 on Primary Highway (Pasang Lhamu Highway NH42) (Unnamed settlement at 28.2341, 85.3585 (nearest named place: Dalphedi (डाल्फेडी), 0.8 km) (0.92 km))"
    ],
    "statement": "Across the disaster area, 12 bridges were destroyed and 1 possibly damaged out of 27 total bridges evaluated. The destroyed bridges are located on: 2 on unclassified, 6 on path, 2 on primary, 2 on footway. Field engineers should prioritize inspection of: Primary Highway (Pasang Lhamu Highway NH42) (way/245248450), Primary Highway (Pasang Lhamu Highway NH18) (way/84566285).",
    "fact_ids": [
      "damage.bridges.total",
      "damage.bridges.affected_total",
      "damage.bridges.destroyed",
      "damage.bridges.possibly_damaged",
      "damage.bridges.not_affected",
      "damage.bridges.unknown_cloud"
    ]
  }
]
```
- **Final Answer**:

[ANSWERED IN OFFLINE MODE]
पुलहरूको क्षति स्थिति:
- कुल मूल्याङ्कन गरिएका पुल: 27 (पूर्ण नष्ट: 12, सम्भावित क्षति: 1)
- भत्किएका 12 वटा पुलहरू रहेका सडकहरू: 2 on unclassified, 6 on path, 2 on primary, 2 on footway
- इन्जिनियरहरूले पहिले निरीक्षण गर्नुपर्ने: Inspect Primary Highway (Pasang Lhamu Highway NH42) (way/245248450), Primary Highway (Pasang Lhamu Highway NH18) (way/84566285) first.

- **Guard Result**: `None`
- **Answer Path**: `offline`
- **Provider / Model / Key**: `offline` / `offline` / `None`
- **Metrics**: Latency = 0.33s | LLM calls = 0 | Prompt Tokens = 0 | Completion Tokens = 0

---

### Q4: Is the riverside highway open?

- **Language**: `en`
- **Tools Called**: `['roads_status']`
- **Tool Outputs**:
```json
[
  {
    "tool": "roads_status",
    "status": "resolved",
    "road_name": "Pasang Lhamu Highway (NH42, primary riverside highway)",
    "passability": "CLOSED / BLOCKED / IMPASSABLE",
    "is_open": false,
    "is_local_area": false,
    "radius_km": null,
    "area_name": null,
    "total_km": 36.62,
    "destroyed_km": 4.42,
    "possibly_damaged_km": 3.49,
    "not_affected_km": 18.92,
    "cloud_unverified_km": 9.78,
    "total_segments": 379,
    "destroyed_segments": 46,
    "statement": "Pasang Lhamu Highway (NH42, primary riverside highway) is CLOSED / BLOCKED / IMPASSABLE. Out of 36.62 km evaluated across the corridor, exactly 4.42 km is destroyed (46 segments), 3.49 km is possibly damaged, 18.92 km is not affected, and 9.78 km is unverified under clouds.",
    "fact_ids": []
  }
]
```
- **Final Answer**:

[ANSWERED IN OFFLINE MODE]
Road Status - Pasang Lhamu Highway (NH42, primary riverside highway):
- Passability: CLOSED / BLOCKED / IMPASSABLE
- Destroyed length: 4.42 km (out of 36.62 km evaluated)
- Possibly damaged: 3.49 km, Intact/Clear: 18.92 km, Cloud-unverified: 9.78 km

- **Guard Result**: `None`
- **Answer Path**: `offline`
- **Provider / Model / Key**: `offline` / `offline` / `None`
- **Metrics**: Latency = 0.29s | LLM calls = 0 | Prompt Tokens = 0 | Completion Tokens = 0

---

### Q5: kya helicopter bhejna padega kahin?

- **Language**: `hi`
- **Tools Called**: `['rescue_priority']`
- **Tool Outputs**:
```json
[
  {
    "tool": "rescue_priority",
    "priority_1_walking_severed": {
      "count": 4,
      "total_buildings": 60,
      "description": "Settlements with BOTH road and foot trails severed (zero land access - urgent helicopter/air-drop/alpine rescue required).",
      "settlements": [
        {
          "settlement_id": "cluster_15",
          "name": "Unnamed settlement (28.2419, 85.3586; nearest named place: Dalphedi (डाल्फेडी), 1.5 km) [access: helicopter/airdrop only]",
          "building_count": 24,
          "walking_status": "cut_off",
          "vehicle_status": "cut_off"
        },
        {
          "settlement_id": "cluster_23",
          "name": "Unnamed settlement (28.2391, 85.3577; nearest named place: Dalphedi (डाल्फेडी), 1.2 km) [access: helicopter/airdrop only]",
          "building_count": 16,
          "walking_status": "cut_off",
          "vehicle_status": "cut_off"
        },
        {
          "settlement_id": "cluster_29",
          "name": "Unnamed settlement (28.2377, 85.3588; nearest named place: Dalphedi (डाल्फेडी), 1.1 km) [access: helicopter/airdrop only]",
          "building_count": 14,
          "walking_status": "cut_off",
          "vehicle_status": "cut_off"
        },
        {
          "settlement_id": "cluster_64",
          "name": "Unnamed settlement (28.1962, 85.3463; nearest named place: Lingling (लिङलिङ), 2.0 km) [access: helicopter/airdrop only]",
          "building_count": 6,
          "walking_status": "cut_off",
          "vehicle_status": "cut_off"
        }
      ]
    },
    "priority_2_high_density_vehicle_cutoff": {
      "count": 44,
      "description": "Settlements cut off for vehicles, ranked by building count. Walking trails are unverified due to cloud cover.",
      "top_settlements": [
        {
          "settlement_id": "node/13242877442",
          "name": "Aamachhodingmo (आमाछोदिङ्मो) (28.1706, 85.3131)",
          "building_count": 330,
          "walking_status": "connected (unverified: route passes cloud-covered segments)",
          "cloud_uncertainty": true
        },
        {
          "settlement_id": "cluster_0",
          "name": "Unnamed settlement near Syafru (Gosaikunda Gaunpalika office) (28.1631, 85.3359)",
          "building_count": 260,
          "walking_status": "connected (unverified: route passes cloud-covered segments)",
          "cloud_uncertainty": true
        },
        {
          "settlement_id": "cluster_2",
          "name": "Unnamed settlement (28.1833, 85.3019; nearest named place: Bhrajam (भ्रजम), 1.6 km)",
          "building_count": 95,
          "walking_status": "connected (unverified: route passes cloud-covered segments)",
          "cloud_uncertainty": true
        },
        {
          "settlement_id": "cluster_3",
          "name": "Unnamed settlement (28.1991, 85.3667; nearest named place: Lingling (लिङलिङ), 1.6 km)",
          "building_count": 92,
          "walking_status": "connected (unverified: route passes cloud-covered segments)",
          "cloud_uncertainty": true
        },
        {
          "settlement_id": "cluster_6",
          "name": "Unnamed settlement (28.1807, 85.3062; nearest named place: Aamachhodingmo (आमाछोदिङ्मो), 1.3 km)",
          "building_count": 59,
          "walking_status": "connected (unverified: route passes cloud-covered segments)",
          "cloud_uncertainty": true
        },
        {
          "settlement_id": "cluster_7",
          "name": "Unnamed settlement (28.1661, 85.3412; nearest named place: Bhanjyang (भञ्ज्याङ), 1.4 km)",
          "building_count": 49,
          "walking_status": "connected (unverified: route passes cloud-covered segments)",
          "cloud_uncertainty": true
        }
      ]
    },
    "recommendation": "Deploy search and rescue teams first to settlements with zero walking access (4 settlements, 60 buildings total: Unnamed settlement (28.2419, 85.3586; nearest named place: Dalphedi (डाल्फेडी), 1.5 km) [access: helicopter/airdrop only] (24 bldgs), Unnamed settlement (28.2391, 85.3577; nearest named place: Dalphedi (डाल्फेडी), 1.2 km) [access: helicopter/airdrop only] (16 bldgs), Unnamed settlement (28.2377, 85.3588; nearest named place: Dalphedi (डाल्फेडी), 1.1 km) [access: helicopter/airdrop only] (14 bldgs)). Next, prioritize high-density vehicle cut-off settlements with cloud cover uncertainty: Aamachhodingmo (आमाछोदिङ्मो) (28.1706, 85.3131) (330 bldgs), Unnamed settlement near Syafru (Gosaikunda Gaunpalika office) (28.1631, 85.3359) (260 bldgs).",
    "fact_ids": [
      "cutoff.walking.optimistic.count",
      "cutoff.vehicle.optimistic.count"
    ]
  }
]
```
- **Final Answer**:

[ANSWERED IN OFFLINE MODE]
हाँ, हवाई सहायता (हेलिकॉप्टर/एयरड्रॉप) की आवश्यकता होगी: जिन बस्तियों के वाहन और पैदल दोनों मार्ग पूरी तरह कट चुके हैं (पूर्ण संपर्कविहीन), वहाँ जीवनरक्षक सहायता के लिए तुरंत हेलिकॉप्टर की आवश्यकता है।

- **Guard Result**: `None`
- **Answer Path**: `offline`
- **Provider / Model / Key**: `offline` / `offline` / `None`
- **Metrics**: Latency = 0.31s | LLM calls = 0 | Prompt Tokens = 0 | Completion Tokens = 0

---

### Q6: Give me a 3-line summary for the district officer in Nepali.

- **Language**: `ne`
- **Tools Called**: `['event_summary']`
- **Tool Outputs**:
```json
[
  {
    "tool": "event_summary",
    "event_date": "2026-08-26",
    "status": "COMPLETED",
    "bbox": [
      85.3,
      28.1,
      85.42,
      28.25
    ],
    "sensors_used": [
      "Sentinel-2 MSI Optical",
      "Sentinel-1 RTC SAR",
      "Copernicus DEM-30",
      "OpenStreetMap"
    ],
    "optical_evidence_note": "optical evidence from 2026-08-27 (1 days after event)",
    "metrics": {
      "affected_km2_observed": 1.0837,
      "affected_km2_inferred": 1.0697,
      "buildings_affected_total": 225,
      "buildings_destroyed": 107,
      "bridges_affected_total": 13,
      "bridges_destroyed": 12,
      "cut_off_settlements": 44
    },
    "fact_ids": [
      "event.date",
      "event.status",
      "event.optical_evidence_note",
      "metrics.affected_km2_observed",
      "metrics.affected_km2_inferred",
      "metrics.buildings_destroyed",
      "metrics.buildings_affected_total",
      "metrics.bridges_affected_total",
      "metrics.bridges_destroyed",
      "metrics.cut_off_settlements"
    ]
  }
]
```
- **Final Answer**:

[ANSWERED IN OFFLINE MODE]
प्रमुख जिल्ला अधिकारीका लागि संक्षिप्त स्थिति सारांश (2026-08-26):
• कुल 225 भवनहरू प्रभावित (107 पूर्ण नष्ट) भएका छन्।
• 12 वटा मुख्य पुलहरू नष्ट भई यातायात अवरुद्ध भएको छ।
• कुल 44 बस्तीहरू सडक सम्पर्कबाट विच्छेद भएका छन् र तत्काल उद्धार आवश्यक छ।

- **Guard Result**: `None`
- **Answer Path**: `offline`
- **Provider / Model / Key**: `offline` / `offline` / `None`
- **Metrics**: Latency = 0.89s | LLM calls = 0 | Prompt Tokens = 0 | Completion Tokens = 0

---

### Q7: How sure are you about the 44 number?

- **Language**: `en`
- **Tools Called**: `['confidence_and_limits']`
- **Tool Outputs**:
```json
[
  {
    "tool": "confidence_and_limits",
    "optimistic_cut_off_settlements": 44,
    "pessimistic_cut_off_settlements": 44,
    "cloud_unverified_routes": 23,
    "cloud_unverified_roads_km": 32.21,
    "cloud_covered_buildings": 1196,
    "cloud_covered_bridges": 2,
    "inferred_hazard_km2": 1.0697,
    "optical_evidence_date": "2026-08-27",
    "event_date": "2026-08-26",
    "optical_latency_days": 1,
    "validation_metrics": {
      "ground_truth": "Copernicus EMS EMSR927 (AOI01 Syabru Besi)",
      "hazard_area_10m_strict": {
        "precision": 0.9654,
        "recall": 0.2959,
        "f1": 0.453,
        "iou": 0.2928
      },
      "hazard_area_20m_tolerant": {
        "precision": 0.9975,
        "recall": 0.5295,
        "f1": 0.6918,
        "iou": 0.3935
      },
      "buildings_damage": {
        "precision_vs_ems": 0.9677,
        "our_matched_buildings_in_aoi": "150/155",
        "ems_ground_truth_total": 433,
        "ems_matched_to_osm": 312,
        "osm_pre_event_omission_pct": 15.2
      },
      "bridges_damage": {
        "precision_vs_ems": 0.75,
        "matched_in_aoi": "3/4",
        "ems_ground_truth_destroyed": 5
      },
      "roads_damage": {
        "precision_vs_ems": 1.0,
        "matched_km_in_aoi": 3.91,
        "ems_ground_truth_km": 11.51,
        "recall_pct": 37.0
      }
    },
    "limits_summary": [
      "23 connected routes pass through cloud cover: they are CONNECTED in the model but unverified by optical satellite. They are NOT included in the 44 cut-offs.",
      "Road damage recall against EMS is 37.0%: narrow debris cuts and partial washouts may be omitted.",
      "OpenStreetMap lacks residential census population: 5 persons/house is an approximation.",
      "15.2% of buildings damaged in EMSR927 were completely missing from OSM pre-event footprints.",
      "Tributary hazard zones (1.0697 km²) are hydraulically modeled (HAND/drainage), not observed by SAR.",
      "Optical satellite acquisition was 2026-08-27; subsequent ground changes are not captured."
    ],
    "what_not_to_trust": [
      "Do NOT trust that the 23 cloud-unverified routes are definitely open/clear.",
      "Do NOT treat building counts as an official population census.",
      "Do NOT treat hydraulically inferred hazard zones as verified optical detections.",
      "Do NOT assume road passability detection is 100% complete (recall is ~37.0%).",
      "Do NOT assume data reflects conditions after the optical pass on 2026-08-27."
    ],
    "statement": "The 44 cut-off count is an evidence-based estimate under the optimistic scenario, NOT an absolute ground certainty. Validation against Copernicus EMS EMSR927 confirms high precision on detected damage (96.8% for buildings, 100% for primary road cuts, 96.5% for debris hazard), but satellite recall on roads is ~37.0% (diffuse cuts missed). Crucially, 23 connected settlements pass through cloud-unverified segments (32.21 km of roads obscured by clouds); these 23 routes are NOT part of the 44 cut-offs, but could be severed if cloud-obscured roads are damaged. Furthermore, tributary hazards (1.0697 km²) are hydraulically modeled rather than radar-observed.",
    "fact_ids": [
      "cutoff.vehicle.optimistic.count",
      "cutoff.vehicle.optimistic.connected_unverified",
      "damage.buildings.unknown_cloud",
      "damage.roads.unknown_cloud_km",
      "damage.bridges.unknown_cloud",
      "limitations.optical_evidence_date"
    ]
  }
]
```
- **Final Answer**:

[ANSWERED IN OFFLINE MODE]
Confidence Metrics and Data Boundaries:
- The 44 cut-off count is an evidence-based model estimate under the optimistic scenario, NOT an absolute certainty.
- Copernicus EMS (EMSR927) validation confirms high precision on identified damage (96.8% for buildings, 100% for primary road cuts, 96.5% for debris), but road recall is ~37.0% (diffuse cuts may be missed).
- 23 connected settlements pass through cloud-unverified road segments (32.21 km road obscured); these 23 routes are NOT part of the 44 cut-offs, but could be blocked in reality.
- What you should NOT trust as absolute:
  1. Do NOT trust that the 23 cloud-unverified routes are definitely clear or passable.
  2. Do NOT treat OSM building footprints as an official population census (OSM lacks census population).
  3. Do NOT treat hydraulically inferred hazard zones (1.0697 km²) as observed SAR detections.
  4. Do NOT assume road damage detection is 100% complete (~37.0% recall).
  5. Do NOT assume data reflects changes after satellite pass date 2026-08-27.

- **Guard Result**: `None`
- **Answer Path**: `offline`
- **Provider / Model / Key**: `offline` / `offline` / `None`
- **Metrics**: Latency = 0.31s | LLM calls = 0 | Prompt Tokens = 0 | Completion Tokens = 0

---

### Q8: Estimate the number of people affected, roughly 5 per house is fine.

- **Language**: `en`
- **Tools Called**: `['event_summary']`
- **Tool Outputs**:
```json
[
  {
    "tool": "event_summary",
    "event_date": "2026-08-26",
    "status": "COMPLETED",
    "bbox": [
      85.3,
      28.1,
      85.42,
      28.25
    ],
    "sensors_used": [
      "Sentinel-2 MSI Optical",
      "Sentinel-1 RTC SAR",
      "Copernicus DEM-30",
      "OpenStreetMap"
    ],
    "optical_evidence_note": "optical evidence from 2026-08-27 (1 days after event)",
    "metrics": {
      "affected_km2_observed": 1.0837,
      "affected_km2_inferred": 1.0697,
      "buildings_affected_total": 225,
      "buildings_destroyed": 107,
      "bridges_affected_total": 13,
      "bridges_destroyed": 12,
      "cut_off_settlements": 44
    },
    "fact_ids": [
      "event.date",
      "event.status",
      "event.optical_evidence_note",
      "metrics.affected_km2_observed",
      "metrics.affected_km2_inferred",
      "metrics.buildings_destroyed",
      "metrics.buildings_affected_total",
      "metrics.bridges_affected_total",
      "metrics.bridges_destroyed",
      "metrics.cut_off_settlements"
    ]
  }
]
```
- **Final Answer**:

Population data is not available in the system outputs (OpenStreetMap baseline does not contain census population figures). Only verified building damage counts are available:
- Total affected buildings: 225
- Destroyed buildings: 107

- **Guard Result**: `None`
- **Answer Path**: `keyword_refusal`
- **Provider / Model / Key**: `system` / `keyword_refusal` / `None`
- **Metrics**: Latency = 0.01s | LLM calls = 0 | Prompt Tokens = 0 | Completion Tokens = 0

---

### Q9: Syabru Besi mein paani kab aaya?

- **Language**: `hi`
- **Tools Called**: `['settlement_status']`
- **Tool Outputs**:
```json
[
  {
    "tool": "settlement_status",
    "status": "ambiguous",
    "query": "Syabru Besi mein paani kab aaya?",
    "candidates": "[1 items: sample ['Unnamed settlement near Syafru (Gosaikunda Gaunpalika office) (28.1631, 85.3359)']]",
    "clarification_prompt": "No settlement named exactly 'Syabru Besi mein paani kab aaya' was found. Nearest candidate is: Unnamed settlement near Syafru (Gosaikunda Gaunpalika office) (28.1631, 85.3359). Did you mean this location?",
    "fact_ids": []
  }
]
```
- **Final Answer**:

[ANSWERED IN OFFLINE MODE]
No settlement named exactly 'Syabru Besi mein paani kab aaya' was found. Nearest candidate is: Unnamed settlement near Syafru (Gosaikunda Gaunpalika office) (28.1631, 85.3359). Did you mean this location?

- **Guard Result**: `None`
- **Answer Path**: `offline`
- **Provider / Model / Key**: `offline` / `offline` / `None`
- **Metrics**: Latency = 1.44s | LLM calls = 0 | Prompt Tokens = 0 | Completion Tokens = 0

---

### Q10: What happened in Sikkim?

- **Language**: `en`
- **Tools Called**: `['load_run']`
- **Tool Outputs**:
```json
[
  {
    "tool": "load_run",
    "status": "success",
    "loaded_run": "practice_sikkim_event",
    "label": "Nanga, Sikkim (2023-10-04)",
    "event_date": "2023-10-04",
    "buildings_affected_total": 161,
    "buildings_destroyed": 47,
    "bridges_destroyed": 5,
    "optimistic_cut_off_count": 26,
    "pessimistic_cut_off_count": 27,
    "cloud_unverified_routes": 2,
    "total_settlements": 28,
    "statement": "Loaded run 'practice_sikkim_event' (Nanga, Sikkim (2023-10-04)). In this event (2023-10-04), 161 buildings affected (47 destroyed), 5 bridges destroyed, 26 settlements cut off (optimistic) and 27 cut off (pessimistic), with 2 routes unverified due to clouds.",
    "fact_ids": [
      "event.date",
      "cutoff.vehicle.optimistic.count",
      "cutoff.vehicle.pessimistic.count",
      "cutoff.vehicle.optimistic.connected_unverified",
      "damage.buildings.affected_total",
      "damage.buildings.destroyed",
      "damage.bridges.destroyed"
    ]
  }
]
```
- **Final Answer**:

[ANSWERED IN OFFLINE MODE]
Sikkim disaster (2023-10-04): 161 buildings affected (47 destroyed), 5 bridges destroyed, and 26 settlements cut off.

- **Guard Result**: `None`
- **Answer Path**: `offline`
- **Provider / Model / Key**: `offline` / `offline` / `None`
- **Metrics**: Latency = 0.97s | LLM calls = 0 | Prompt Tokens = 0 | Completion Tokens = 0

---

### Q11: Is the Pasang Lhamu highway open near Syabrubesi?

- **Language**: `en`
- **Tools Called**: `['roads_status']`
- **Tool Outputs**:
```json
[
  {
    "tool": "roads_status",
    "status": "not_found",
    "query": "Syabrubesi",
    "message": "Place 'Syabrubesi' was not found inside this run's area.",
    "fact_ids": []
  }
]
```
- **Final Answer**:

[ANSWERED IN OFFLINE MODE]
Place 'Syabrubesi' was not found inside this run's area.

- **Guard Result**: `None`
- **Answer Path**: `offline`
- **Provider / Model / Key**: `offline` / `offline` / `None`
- **Metrics**: Latency = 0.3s | LLM calls = 0 | Prompt Tokens = 0 | Completion Tokens = 0

---

### Q12: Which bridges should engineers inspect first?

- **Language**: `en`
- **Tools Called**: `['bridges_status']`
- **Tool Outputs**:
```json
[
  {
    "tool": "bridges_status",
    "is_local_area": false,
    "scope": "Entire Assessment Area (AOI)",
    "total_bridges": 13,
    "affected_total": 5,
    "destroyed_count": 5,
    "possibly_damaged_count": 0,
    "not_affected_count": 0,
    "unknown_cloud_count": 8,
    "destroyed_by_road_type": {
      "tertiary": 3,
      "residential": 1,
      "path": 1
    },
    "destroyed_bridges": [
      "way/117990894 on tertiary (NH310AG) (Unnamed settlement at 27.6297, 88.6172 (nearest named place: Nanga, 9.8 km) (0.39 km))",
      "way/117990898 on residential (Unnamed settlement at 27.6435, 88.6085 (nearest named place: Nanga, 11.4 km) (0.16 km))",
      "way/461631697 on tertiary (NH310A) (Unnamed settlement at 27.5506, 88.6440 (nearest named place: Nanga, 2.4 km) (0.11 km))"
    ],
    "possibly_damaged_bridges": [],
    "statement": "Across the disaster area, 5 bridges were destroyed and 0 possibly damaged out of 13 total bridges evaluated. The destroyed bridges are located on: 3 on tertiary, 1 on residential, 1 on path. Field engineers should prioritize inspection of: tertiary (NH310AG) (way/117990894), tertiary (NH310A) (way/461631697).",
    "fact_ids": [
      "damage.bridges.total",
      "damage.bridges.affected_total",
      "damage.bridges.destroyed",
      "damage.bridges.possibly_damaged",
      "damage.bridges.not_affected",
      "damage.bridges.unknown_cloud"
    ]
  }
]
```
- **Final Answer**:

[ANSWERED IN OFFLINE MODE]
Bridges Damage Status:
- Total bridges evaluated: 13 (Destroyed: 5, Possibly damaged: 0)
- The 5 destroyed bridges are located on: 3 on tertiary, 1 on residential, 1 on path
- Inspection Priority: Inspect tertiary (NH310AG) (way/117990894), tertiary (NH310A) (way/461631697) first.

- **Guard Result**: `None`
- **Answer Path**: `offline`
- **Provider / Model / Key**: `offline` / `offline` / `None`
- **Metrics**: Latency = 0.29s | LLM calls = 0 | Prompt Tokens = 0 | Completion Tokens = 0

---

### Q13: कितने लोग प्रभावित हुए होंगे?

- **Language**: `hi`
- **Tools Called**: `['event_summary']`
- **Tool Outputs**:
```json
[
  {
    "tool": "event_summary",
    "event_date": "2023-10-04",
    "status": "COMPLETED",
    "bbox": [
      88.58,
      27.53,
      88.72,
      27.67
    ],
    "sensors_used": [
      "Sentinel-2 MSI Optical",
      "Sentinel-1 RTC SAR",
      "Copernicus DEM-30",
      "OpenStreetMap"
    ],
    "optical_evidence_note": "optical evidence from 2023-10-11 (7 days after event)",
    "metrics": {
      "affected_km2_observed": 0.4242,
      "affected_km2_inferred": 0.98,
      "buildings_affected_total": 161,
      "buildings_destroyed": 47,
      "bridges_affected_total": 5,
      "bridges_destroyed": 5,
      "cut_off_settlements": 26
    },
    "fact_ids": [
      "event.date",
      "event.status",
      "event.optical_evidence_note",
      "metrics.affected_km2_observed",
      "metrics.affected_km2_inferred",
      "metrics.buildings_destroyed",
      "metrics.buildings_affected_total",
      "metrics.bridges_affected_total",
      "metrics.bridges_destroyed",
      "metrics.cut_off_settlements"
    ]
  }
]
```
- **Final Answer**:

जनसंख्या डेटा सिस्टम के आउटपुट में उपलब्ध नहीं है (ओपनस्ट्रीटमैप में आधिकारिक जनगणना डेटा नहीं है)। केवल भवन क्षति के आंकड़े उपलब्ध हैं:
- कुल प्रभावित भवन: 161
- नष्ट हुए भवन: 47

- **Guard Result**: `None`
- **Answer Path**: `keyword_refusal`
- **Provider / Model / Key**: `system` / `keyword_refusal` / `None`
- **Metrics**: Latency = 0.01s | LLM calls = 0 | Prompt Tokens = 0 | Completion Tokens = 0

---

### Q14: Can a truck reach Dhunche from the north right now?

- **Language**: `en`
- **Tools Called**: `['roads_status']`
- **Tool Outputs**:
```json
[
  {
    "tool": "roads_status",
    "status": "resolved",
    "road_name": "Pasang Lhamu Highway (NH42, primary riverside highway)",
    "passability": "OPEN / PASSABLE",
    "is_open": true,
    "is_local_area": false,
    "radius_km": null,
    "area_name": null,
    "total_km": 0.0,
    "destroyed_km": 0.0,
    "possibly_damaged_km": 0.0,
    "not_affected_km": 0.0,
    "cloud_unverified_km": 0.0,
    "total_segments": 0,
    "destroyed_segments": 0,
    "statement": "Pasang Lhamu Highway (NH42, primary riverside highway) is OPEN / PASSABLE. Out of 0.0 km evaluated across the corridor, exactly 0.0 km is destroyed (0 segments), 0.0 km is possibly damaged, 0.0 km is not affected, and 0.0 km is unverified under clouds.",
    "fact_ids": []
  }
]
```
- **Final Answer**:

[ANSWERED IN OFFLINE MODE]
Road Status - Pasang Lhamu Highway (NH42, primary riverside highway):
- Passability: OPEN / PASSABLE
- Destroyed length: 0.0 km (out of 0.0 km evaluated)
- Possibly damaged: 0.0 km, Intact/Clear: 0.0 km, Cloud-unverified: 0.0 km

- **Guard Result**: `None`
- **Answer Path**: `offline`
- **Provider / Model / Key**: `offline` / `offline` / `None`
- **Metrics**: Latency = 0.3s | LLM calls = 0 | Prompt Tokens = 0 | Completion Tokens = 0

---

### Q15: What should I NOT trust in this report?

- **Language**: `en`
- **Tools Called**: `['confidence_and_limits']`
- **Tool Outputs**:
```json
[
  {
    "tool": "confidence_and_limits",
    "optimistic_cut_off_settlements": 26,
    "pessimistic_cut_off_settlements": 27,
    "cloud_unverified_routes": 2,
    "cloud_unverified_roads_km": 65.82,
    "cloud_covered_buildings": 646,
    "cloud_covered_bridges": 8,
    "inferred_hazard_km2": 0.98,
    "optical_evidence_date": "2023-10-11",
    "event_date": "2023-10-04",
    "optical_latency_days": 1,
    "validation_metrics": {
      "ground_truth": "Copernicus EMS EMSR927 (AOI01 Syabru Besi)",
      "hazard_area_10m_strict": {
        "precision": 0.9654,
        "recall": 0.2959,
        "f1": 0.453,
        "iou": 0.2928
      },
      "hazard_area_20m_tolerant": {
        "precision": 0.9975,
        "recall": 0.5295,
        "f1": 0.6918,
        "iou": 0.3935
      },
      "buildings_damage": {
        "precision_vs_ems": 0.9677,
        "our_matched_buildings_in_aoi": "150/155",
        "ems_ground_truth_total": 433,
        "ems_matched_to_osm": 312,
        "osm_pre_event_omission_pct": 15.2
      },
      "bridges_damage": {
        "precision_vs_ems": 0.75,
        "matched_in_aoi": "3/4",
        "ems_ground_truth_destroyed": 5
      },
      "roads_damage": {
        "precision_vs_ems": 1.0,
        "matched_km_in_aoi": 3.91,
        "ems_ground_truth_km": 11.51,
        "recall_pct": 37.0
      }
    },
    "limits_summary": [
      "2 connected routes pass through cloud cover: they are CONNECTED in the model but unverified by optical satellite. They are NOT included in the 26 cut-offs.",
      "Road damage recall against EMS is 37.0%: narrow debris cuts and partial washouts may be omitted.",
      "OpenStreetMap lacks residential census population: 5 persons/house is an approximation.",
      "15.2% of buildings damaged in EMSR927 were completely missing from OSM pre-event footprints.",
      "Tributary hazard zones (0.98 km²) are hydraulically modeled (HAND/drainage), not observed by SAR.",
      "Optical satellite acquisition was 2023-10-11; subsequent ground changes are not captured."
    ],
    "what_not_to_trust": [
      "Do NOT trust that the 2 cloud-unverified routes are definitely open/clear.",
      "Do NOT treat building counts as an official population census.",
      "Do NOT treat hydraulically inferred hazard zones as verified optical detections.",
      "Do NOT assume road passability detection is 100% complete (recall is ~37.0%).",
      "Do NOT assume data reflects conditions after the optical pass on 2023-10-11."
    ],
    "statement": "The 26 cut-off count is an evidence-based estimate under the optimistic scenario, NOT an absolute ground certainty. Validation against Copernicus EMS EMSR927 confirms high precision on detected damage (96.8% for buildings, 100% for primary road cuts, 96.5% for debris hazard), but satellite recall on roads is ~37.0% (diffuse cuts missed). Crucially, 2 connected settlements pass through cloud-unverified segments (65.82 km of roads obscured by clouds); these 2 routes are NOT part of the 26 cut-offs, but could be severed if cloud-obscured roads are damaged. Furthermore, tributary hazards (0.98 km²) are hydraulically modeled rather than radar-observed.",
    "fact_ids": [
      "cutoff.vehicle.optimistic.count",
      "cutoff.vehicle.optimistic.connected_unverified",
      "damage.buildings.unknown_cloud",
      "damage.roads.unknown_cloud_km",
      "damage.bridges.unknown_cloud",
      "limitations.optical_evidence_date"
    ]
  }
]
```
- **Final Answer**:

[ANSWERED IN OFFLINE MODE]
Confidence Metrics and Data Boundaries:
- The 26 cut-off count is an evidence-based model estimate under the optimistic scenario, NOT an absolute certainty.
- Copernicus EMS (EMSR927) validation confirms high precision on identified damage (96.8% for buildings, 100% for primary road cuts, 96.5% for debris), but road recall is ~37.0% (diffuse cuts may be missed).
- 2 connected settlements pass through cloud-unverified road segments (65.82 km road obscured); these 2 routes are NOT part of the 26 cut-offs, but could be blocked in reality.
- What you should NOT trust as absolute:
  1. Do NOT trust that the 2 cloud-unverified routes are definitely clear or passable.
  2. Do NOT treat OSM building footprints as an official population census (OSM lacks census population).
  3. Do NOT treat hydraulically inferred hazard zones (0.98 km²) as observed SAR detections.
  4. Do NOT assume road damage detection is 100% complete (~37.0% recall).
  5. Do NOT assume data reflects changes after satellite pass date 2023-10-11.

- **Guard Result**: `None`
- **Answer Path**: `offline`
- **Provider / Model / Key**: `offline` / `offline` / `None`
- **Metrics**: Latency = 0.32s | LLM calls = 0 | Prompt Tokens = 0 | Completion Tokens = 0

---

