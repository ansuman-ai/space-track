# Held-Out Evaluation v3: openai/gpt-4o-mini

- **Disaster Run:** `test_A_cold_final2_run1` (Trishuli 2026-08-26)
- **Provider:** `openai_compatible`
- **Model:** `openai/gpt-4o-mini`
- **Total Latency:** `52.58s` (avg `5.26s`/turn)
- **Guard Violations:** `1` / 10
- **Language Correct:** `10` / 10
- **Tools Called:** `10` / 10

---

### Q1: Which villages can't reach the hospital by car right now?
- **Expected Language:** `en` | **Detected Language:** `en` | **Language Correct:** `True`
- **Latency:** `10.44s`
- **NumberGuard Passed:** `True` (violating: `[]`)
- **Tools Called:** `["cutoff_settlements({\"network\": \"vehicle\", \"scenario\": \"pessimistic\"})"]`

#### Tool Outputs:
```json
[
  {
    "tool": "cutoff_settlements",
    "network": "vehicle",
    "scenario": "pessimistic",
    "optimistic_cut_off_count": 44,
    "pessimistic_cut_off_count": 44,
    "cloud_unverified_routes": 23,
    "scenarios_differ": false,
    "cut_off_count": 44,
    "connected_clear_count": 0,
    "connected_unverified_count": 23,
    "connected_total_count": 23,
    "no_network_access_count": 43,
    "evidence": "inferred",
    "cut_off_settlements_sample": [
      {
        "settlement_id": "cluster_0",
        "name": "Unnamed settlement near Syafru (Gosaikunda Gaunpalika office) (28.1631, 85.3359)",
        "building_count": 260
      },
      {
        "settlement_id": "cluster_10",
        "name": "Unnamed settlement near Lingling (Holiday Homestay) (28.2127, 85.3578)",
        "building_count": 35
      },
      {
        "settlement_id": "cluster_14",
        "name": "Unnamed settlement (28.1617, 85.3321; nearest named place: Bahun Danda (बाहुनडाँडा), 1.1 km)",
        "building_count": 25
      },
      {
        "settlement_id": "cluster_15",
        "name": "Unnamed settlement (28.2419, 85.3586; nearest named place: Dalphedi (डाल्फेडी), 1.5 km) [access: helicopter/airdrop only]",
        "building_count": 24
      },
      {
        "settlement_id": "cluster_16",
        "name": "Cluster near Lingling (लिङलिङ) (28.2120, 85.3609)",
        "building_count": 23
      },
      {
        "settlement_id": "cluster_17",
        "name": "Unnamed settlement (28.1915, 85.3432; nearest named place: Pajung (पाजुङ), 1.7 km)",
        "building_count": 21
      },
      {
        "settlement_id": "cluster_18",
        "name": "Unnamed settlement (28.1685, 85.3054; nearest named place: Aamachhodingmo (आमाछोदिङ्मो), 0.8 km)",
        "building_count": 18
      },
      {
        "settlement_id": "cluster_2",
        "name": "Unnamed settlement (28.1833, 85.3019; nearest named place: Bhrajam (भ्रजम), 1.6 km)",
        "building_count": 95
      },
      {
        "settlement_id": "cluster_23",
        "name": "Unnamed settlement (28.2391, 85.3577; nearest named place: Dalphedi (डाल्फेडी), 1.2 km) [access: helicopter/airdrop only]",
        "building_count": 16
      },
      {
        "settlement_id": "cluster_24",
        "name": "Unnamed settlement (28.2008, 85.3682; nearest named place: Lingling (लिङलिङ), 1.5 km)",
        "building_count": 16
      },
      {
        "settlement_id": "cluster_26",
        "name": "Unnamed settlement (28.1918, 85.3108; nearest named place: Bhrajam (भ्रजम), 0.8 km)",
        "building_count": 15
      },
      {
        "settlement_id": "cluster_29",
        "name": "Unnamed settlement (28.2377, 85.3588; nearest named place: Dalphedi (डाल्फेडी), 1.1 km) [access: helicopter/airdrop only]",
        "building_count": 14
      },
      {
        "settlement_id": "cluster_3",
        "name": "Unnamed settlement (28.1991, 85.3667; nearest named place: Lingling (लिङलिङ), 1.6 km)",
        "building_count": 92
      },
      {
        "settlement_id": "cluster_31",
        "name": "Unnamed settlement (28.1609, 85.3298; nearest named place: Bahun Danda (बाहुनडाँडा), 1.0 km)",
        "building_count": 12
      },
      {
        "settlement_id": "cluster_33",
        "name": "Cluster near Lingling (लिङलिङ) (28.2087, 85.3618)",
        "building_count": 11
      }
    ],
    "total_cut_off_settlements": 44,
    "statement": "Under both optimistic and pessimistic scenarios, 44 settlements are cut off from vehicle access (with 23 routes passing through cloud-unverified segments).",
    "fact_ids": [
      "cutoff.vehicle.pessimistic.count",
      "cutoff.vehicle.pessimistic.connected_clear",
      "cutoff.vehicle.pessimistic.connected_unverified",
      "cutoff.vehicle.pessimistic.connected_total",
      "cutoff.vehicle.no_network_access",
      "cutoff.vehicle.optimistic.count",
      "cutoff.vehicle.pessimistic.count"
    ]
  }
]
```

#### Model Answer:
Currently, 44 settlements are cut off from vehicle access. Among these, 23 routes pass through cloud-unverified segments, meaning their passability cannot be confirmed optically. Here are some of the villages that cannot reach the hospital by car:

1. Unnamed settlement near Syafru (Gosaikunda Gaunpalika office) - 260 buildings
2. Unnamed settlement near Lingling (Holiday Homestay) - 35 buildings
3. Unnamed settlement - 25 buildings (nearest named place: Bahun Danda)
4. Unnamed settlement - 24 buildings (nearest named place: Dalphedi, access: helicopter/airdrop only)
5. Cluster near Lingling - 23 buildings
6. Unnamed settlement - 21 buildings (nearest named place: Pajung)
7. Unnamed settlement - 18 buildings (nearest named place: Aamachhodingmo)
8. Unnamed settlement - 95 buildings (nearest named place: Bhrajam)
9. Unnamed settlement - 16 buildings (nearest named place: Dalphedi, access: helicopter/airdrop only)
10. Unnamed settlement - 16 buildings (nearest named place: Lingling)

This is a sample of the settlements affected.

---

### Q2: aur unme se sabse bada kaunsa hai?
- **Expected Language:** `hi` | **Detected Language:** `hi` | **Language Correct:** `True`
- **Latency:** `3.66s`
- **NumberGuard Passed:** `True` (violating: `[]`)
- **Tools Called:** `["rescue_priority({})"]`

#### Tool Outputs:
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

#### Model Answer:
सबसे बड़ा गांव जो अस्पताल तक कार से नहीं पहुँच सकता है, वह है **Aamachhodingmo (आमाछोदिङ्मो)**, जिसमें **330** भवन हैं। यह गांव वाहन पहुंच से कट गया है और इसकी स्थिति में बादल की अनिश्चितता है।

---

### Q3: पुल कतिवटा भत्किए र कुन सडकमा?
- **Expected Language:** `ne` | **Detected Language:** `ne` | **Language Correct:** `True`
- **Latency:** `3.97s`
- **NumberGuard Passed:** `True` (violating: `[]`)
- **Tools Called:** `["bridges_status({\"area\": \"Kathmandu\", \"radius_km\": 1})", "damage_summary({\"area\": \"Kathmandu\", \"radius_km\": 1})"]`

#### Tool Outputs:
```json
[
  {
    "tool": "bridges_status",
    "status": "not_found",
    "query": "Kathmandu",
    "message": "Place 'Kathmandu' was not found inside this run's area.",
    "fact_ids": []
  },
  {
    "tool": "damage_summary",
    "status": "not_found",
    "query": "Kathmandu",
    "message": "Place 'Kathmandu' was not found inside this run's area.",
    "fact_ids": []
  }
]
```

#### Model Answer:
क्षमा गर्नुहोस्, तर "काठमाडौं" स्थान यस घटनाको क्षेत्र भित्र फेला परेन। कृपया अर्को स्थानको बारेमा सोध्नुहोस्।

---

### Q4: Is the riverside highway open?
- **Expected Language:** `en` | **Detected Language:** `en` | **Language Correct:** `True`
- **Latency:** `3.1s`
- **NumberGuard Passed:** `True` (violating: `[]`)
- **Tools Called:** `["damage_summary({\"area\": \"riverside highway\"})"]`

#### Tool Outputs:
```json
[
  {
    "tool": "damage_summary",
    "status": "not_found",
    "query": "riverside highway",
    "message": "Place 'riverside highway' was not found inside this run's area.",
    "fact_ids": []
  }
]
```

#### Model Answer:
The "riverside highway" was not found inside this run's area. Please provide a specific location or name for further assistance.

---

### Q5: kya helicopter bhejna padega kahin?
- **Expected Language:** `hi` | **Detected Language:** `hi` | **Language Correct:** `True`
- **Latency:** `9.58s`
- **NumberGuard Passed:** `False` (violating: `[1, 1.5, 1.2, 1.1, 14, 2]`)
- **Tools Called:** `["rescue_priority({})"]`

#### Tool Outputs:
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

#### Model Answer:
बचाव दल तैनाती प्राथमिकता (SAR Deployment):
- प्राथमिकता १ (पैदल और सड़क दोनों बंद - पूर्ण संपर्कविहीन): 4 बस्तियाँ (60 भवन): Unnamed settlement (28.2419, 85.3586; nearest named place: Dalphedi (डाल्फेडी), 1.5 km) [access: helicopter/airdrop only] (24 bldgs), Unnamed settlement (28.2391, 85.3577; nearest named place: Dalphedi (डाल्फेडी), 1.2 km) [access: helicopter/airdrop only] (16 bldgs), Unnamed settlement (28.2377, 85.3588; nearest named place: Dalphedi (डाल्फेडी), 1.1 km) [access: helicopter/airdrop only] (14 bldgs)।
- प्राथमिकता २ (सड़क संपर्कविहीन, उच्च घनत्व): Aamachhodingmo (आमाछोदिङ्मो) (28.1706, 85.3131) (330 bldgs), Unnamed settlement near Syafru (Gosaikunda Gaunpalika office) (28.1631, 85.3359) (260 bldgs)।

---

### Q6: Give me a 3-line summary for the district officer in Nepali.
- **Expected Language:** `ne` | **Detected Language:** `ne` | **Language Correct:** `True`
- **Latency:** `5.21s`
- **NumberGuard Passed:** `True` (violating: `[]`)
- **Tools Called:** `["event_summary({})"]`

#### Tool Outputs:
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

#### Model Answer:
घटना विवरण (2026-08-26):
- प्रत्यक्ष प्रभावित क्षेत्र: 1.0837 वर्ग किलोमिटर
- पूर्ण रूपमा नष्ट भएका भवनहरू: 107
- नष्ट भएका पुलहरू: 12
- सडक सम्पर्क विच्छेद भएका बस्तीहरू: 44
टिप्पणी: सबै तथ्याङ्क स्याटेलाइट र ओपन्स्ट्रीटम्याप विश्लेषणमा आधारित छन्।

---

### Q7: How sure are you about the 44 number?
- **Expected Language:** `en` | **Detected Language:** `en` | **Language Correct:** `True`
- **Latency:** `4.32s`
- **NumberGuard Passed:** `True` (violating: `[]`)
- **Tools Called:** `["cutoff_settlements({\"network\": \"walking\", \"scenario\": \"optimistic\"})"]`

#### Tool Outputs:
```json
[
  {
    "tool": "cutoff_settlements",
    "network": "walking",
    "scenario": "optimistic",
    "optimistic_cut_off_count": 4,
    "pessimistic_cut_off_count": 4,
    "cloud_unverified_routes": 103,
    "scenarios_differ": false,
    "cut_off_count": 4,
    "connected_clear_count": 0,
    "connected_unverified_count": 103,
    "connected_total_count": 103,
    "no_network_access_count": 3,
    "evidence": "observed",
    "cut_off_settlements_sample": [
      {
        "settlement_id": "cluster_15",
        "name": "Unnamed settlement (28.2419, 85.3586; nearest named place: Dalphedi (डाल्फेडी), 1.5 km) [access: helicopter/airdrop only]",
        "building_count": 24
      },
      {
        "settlement_id": "cluster_23",
        "name": "Unnamed settlement (28.2391, 85.3577; nearest named place: Dalphedi (डाल्फेडी), 1.2 km) [access: helicopter/airdrop only]",
        "building_count": 16
      },
      {
        "settlement_id": "cluster_29",
        "name": "Unnamed settlement (28.2377, 85.3588; nearest named place: Dalphedi (डाल्फेडी), 1.1 km) [access: helicopter/airdrop only]",
        "building_count": 14
      },
      {
        "settlement_id": "cluster_64",
        "name": "Unnamed settlement (28.1962, 85.3463; nearest named place: Lingling (लिङलिङ), 2.0 km) [access: helicopter/airdrop only]",
        "building_count": 6
      }
    ],
    "total_cut_off_settlements": 4,
    "statement": "Under both optimistic and pessimistic scenarios, 4 settlements are cut off from walking access (with 103 routes passing through cloud-unverified segments).",
    "fact_ids": [
      "cutoff.walking.optimistic.count",
      "cutoff.walking.optimistic.connected_clear",
      "cutoff.walking.optimistic.connected_unverified",
      "cutoff.walking.optimistic.connected_total",
      "cutoff.walking.no_network_access",
      "cutoff.walking.optimistic.count",
      "cutoff.walking.pessimistic.count"
    ]
  }
]
```

#### Model Answer:
Cut-Off Settlements (walking network):
- Cut-off settlements (both optimistic and pessimistic): 4
- Cloud-unverified connected routes: 103

---

### Q8: Estimate the number of people affected, roughly 5 per house is fine.
- **Expected Language:** `en` | **Detected Language:** `en` | **Language Correct:** `True`
- **Latency:** `2.29s`
- **NumberGuard Passed:** `True` (violating: `[]`)
- **Tools Called:** `["damage_summary({\"area\": \"Kathmandu\"})"]`

#### Tool Outputs:
```json
[
  {
    "tool": "damage_summary",
    "status": "not_found",
    "query": "Kathmandu",
    "message": "Place 'Kathmandu' was not found inside this run's area.",
    "fact_ids": []
  }
]
```

#### Model Answer:
The place "Kathmandu" was not found inside this run's area. Therefore, I cannot provide an estimate of the number of people affected based on the number of houses.

---

### Q9: Syabru Besi mein paani kab aaya?
- **Expected Language:** `hi` | **Detected Language:** `hi` | **Language Correct:** `True`
- **Latency:** `3.53s`
- **NumberGuard Passed:** `True` (violating: `[]`)
- **Tools Called:** `["nearest_destination({\"name\": \"Syabrubesi\"})"]`

#### Tool Outputs:
```json
[
  {
    "tool": "settlement_status",
    "status": "ambiguous",
    "query": "Syabrubesi",
    "candidates": [
      {
        "settlement_id": "cluster_0",
        "name": "Unnamed settlement near Syafru (Gosaikunda Gaunpalika office) (28.1631, 85.3359)",
        "building_count": 260,
        "vehicle_status": "cut_off"
      }
    ],
    "clarification_prompt": "No settlement named exactly 'Syabrubesi' was found. Nearest candidate is: Unnamed settlement near Syafru (Gosaikunda Gaunpalika office) (28.1631, 85.3359). Did you mean this location?",
    "fact_ids": []
  }
]
```

#### Model Answer:
"Syabrubesi" नामक कुनै बस्ती सटीक रूपमा फेला परेन। नजिकको उम्मेदवार: "Unnamed settlement near Syafru (Gosaikunda Gaunpalika office) (28.1631, 85.3359)" हो। के तपाईंले यस स्थानलाई बुझ्नुभएको हो?

---

### Q10: What happened in Sikkim?
- **Expected Language:** `en` | **Detected Language:** `en` | **Language Correct:** `True`
- **Latency:** `6.48s`
- **NumberGuard Passed:** `True` (violating: `[]`)
- **Tools Called:** `["list_runs({})", "load_run({\"run_name\": \"practice_sikkim_event\"})"]`

#### Tool Outputs:
```json
[
  {
    "tool": "list_runs",
    "active_run": "test_A_cold_final2_run1",
    "available_runs": [
      {
        "run_name": "bench_cold_current_run1",
        "path": "/home/zeus/Downloads/project1/runs/bench_cold_current_run1",
        "label": "ब्राबल / Trishuli River (2026-08-26)",
        "event_date": "2026-08-26",
        "bbox": [
          85.3,
          28.1,
          85.42,
          28.25
        ],
        "data_mode": "COMPLETED",
        "top_places": [
          "ब्राबल",
          "Brabal",
          "आमाछोदिङ्मो",
          "Aamachhodingmo",
          "चंदन बाडी",
          "Chandanbari"
        ],
        "top_waterways": [
          "Trishuli River",
          "Bhote Koshi",
          "Langtang Khola",
          "Chilime Khola"
        ],
        "opt_cutoff": 22,
        "pess_cutoff": 22,
        "unver_routes": 45,
        "buildings_destroyed": 7,
        "mtime": 1791220118.092405
      },
      {
        "run_name": "bench_cold_current_run2",
        "path": "/home/zeus/Downloads/project1/runs/bench_cold_current_run2",
        "label": "ब्राबल / Trishuli River (2026-08-26)",
        "event_date": "2026-08-26",
        "bbox": [
          85.3,
          28.1,
          85.42,
          28.25
        ],
        "data_mode": "COMPLETED",
        "top_places": [
          "ब्राबल",
          "Brabal",
          "आमाछोदिङ्मो",
          "Aamachhodingmo",
          "बाहुनडाँडा",
          "Bahun Danda"
        ],
        "top_waterways": [
          "Trishuli River",
          "Bhote Koshi",
          "Langtang Khola",
          "Chilime Khola"
        ],
        "opt_cutoff": 14,
        "pess_cutoff": 14,
        "unver_routes": 53,
        "buildings_destroyed": 3,
        "mtime": 1791223758.7727597
      },
      {
        "run_name": "bench_cold_current_run3",
        "path": "/home/zeus/Downloads/project1/runs/bench_cold_current_run3",
        "label": "ब्राबल / Trishuli River (2026-08-26)",
        "event_date": "2026-08-26",
        "bbox": [
          85.3,
          28.1,
          85.42,
          28.25
        ],
        "data_mode": "COMPLETED",
        "top_places": [
          "ब्राबल",
          "Brabal",
          "आमाछोदिङ्मो",
          "Aamachhodingmo",
          "बाहुनडाँडा",
          "Bahun Danda"
        ],
        "top_waterways": [
          "Trishuli River",
          "Bhote Koshi",
          "Langtang Khola",
          "Chilime Khola"
        ],
        "opt_cutoff": 14,
        "pess_cutoff": 14,
        "unver_routes": 53,
        "buildings_destroyed": 3,
        "mtime": 1791224380.4561427
      },
      {
        "run_name": "bench_cold_optimized",
        "path": "/home/zeus/Downloads/project1/runs/bench_cold_optimized",
        "label": "ब्राबल / Trishuli River (2026-08-26)",
        "event_date": "2026-08-26",
        "bbox": [
          85.3,
          28.1,
          85.42,
          28.25
        ],
        "data_mode": "COMPLETED",
        "top_places": [
          "ब्राबल",
          "Brabal",
          "आमाछोदिङ्मो",
          "Aamachhodingmo",
          "चंदन बाडी",
          "Chandanbari"
        ],
        "top_waterways": [
          "Trishuli River",
          "Bhote Koshi",
          "Langtang Khola",
          "Chilime Khola"
        ],
        "opt_cutoff": 22,
        "pess_cutoff": 22,
        "unver_routes": 45,
        "buildings_destroyed": 16,
        "mtime": 1791229475.867783
      },
      {
        "run_name": "bench_cold_v5",
        "path": "/home/zeus/Downloads/project1/runs/bench_cold_v5",
        "label": "ब्राबल / Trishuli River (2026-08-26)",
        "event_date": "2026-08-26",
        "bbox": [
          85.3,
          28.1,
          85.42,
          28.25
        ],
        "data_mode": "COMPLETED",
        "top_places": [
          "ब्राबल",
          "Brabal",
          "आमाछोदिङ्मो",
          "Aamachhodingmo",
          "बाहुनडाँडा",
          "Bahun Danda"
        ],
        "top_waterways": [
          "Trishuli River",
          "Bhote Koshi",
          "Langtang Khola",
          "Chilime Khola"
        ],
        "opt_cutoff": 22,
        "pess_cutoff": 22,
        "unver_routes": 45,
        "buildings_destroyed": 7,
        "mtime": 1791199713.8933225
      },
      {
        "run_name": "bench_cold_v5_run1",
        "path": "/home/zeus/Downloads/project1/runs/bench_cold_v5_run1",
        "label": "ब्राबल / Trishuli River (2026-08-26)",
        "event_date": "2026-08-26",
        "bbox": [
          85.3,
          28.1,
          85.42,
          28.25
        ],
        "data_mode": "COMPLETED",
        "top_places": [
          "ब्राबल",
          "Brabal",
          "आमाछोदिङ्मो",
          "Aamachhodingmo",
          "बाहुनडाँडा",
          "Bahun Danda"
        ],
        "top_waterways": [
          "Trishuli River",
          "Bhote Koshi",
          "Langtang Khola",
          "Chilime Khola"
        ],
        "opt_cutoff": 22,
        "pess_cutoff": 22,
        "unver_routes": 45,
        "buildings_destroyed": 7,
        "mtime": 1791218583.1381645
      },
      {
        "run_name": "bench_cold_v6",
        "path": "/home/zeus/Downloads/project1/runs/bench_cold_v6",
        "label": "ब्राबल / Trishuli River (2026-08-26)",
        "event_date": "2026-08-26",
        "bbox": [
          85.3,
          28.1,
          85.42,
          28.25
        ],
        "data_mode": "COMPLETED",
        "top_places": [
          "ब्राबल",
          "Brabal",
          "आमाछोदिङ्मो",
          "Aamachhodingmo",
          "चंदन बाडी",
          "Chandanbari"
        ],
        "top_waterways": [
          "Trishuli River",
          "Bhote Koshi",
          "Langtang Khola",
          "Chilime Khola"
        ],
        "opt_cutoff": 22,
        "pess_cutoff": 22,
        "unver_routes": 45,
        "buildings_destroyed": 7,
        "mtime": 1791213460.4506528
      },
      {
        "run_name": "control",
        "path": "/home/zeus/Downloads/project1/runs/control",
        "label": "control",
        "event_date": "unknown",
        "bbox": null,
        "data_mode": "COMPLETED",
        "top_places": [],
        "top_waterways": [],
        "opt_cutoff": null,
        "pess_cutoff": null,
        "unver_routes": null,
        "buildings_destroyed": 0,
        "mtime": 1791261687.543424
      },
      {
        "run_name": "grid_0.55_A",
        "path": "/home/zeus/Downloads/project1/runs/grid_0.55_A",
        "label": "आमाछोदिङ्मो / Bhote Koshi (2026-08-26)",
        "event_date": "2026-08-26",
        "bbox": [
          85.3,
          28.1,
          85.42,
          28.25
        ],
        "data_mode": "COMPLETED",
        "top_places": [
          "आमाछोदिङ्मो",
          "Aamachhodingmo",
          "ब्राबल",
          "Brabal",
          "पाजुङ",
          "Pajung"
        ],
        "top_waterways": [
          "Bhote Koshi",
          "Trishuli River",
          "Langtang Khola",
          "Chilime Khola"
        ],
        "opt_cutoff": 44,
        "pess_cutoff": 44,
        "unver_routes": 23,
        "buildings_destroyed": 107,
        "mtime": 1791276617.3131347
      },
      {
        "run_name": "grid_0.55_B",
        "path": "/home/zeus/Downloads/project1/runs/grid_0.55_B",
        "label": "Melamchi / Indrawati river (2021-06-15)",
        "event_date": "2021-06-15",
        "bbox": [
          85.53,
          27.8,
          85.62,
          27.95
        ],
        "data_mode": "COMPLETED",
        "top_places": [
          "Melamchi",
          "Bansbari",
          "Duwachaur",
          "Talamarang",
          "Langarche",
          "Sikharpur"
        ],
        "top_waterways": [
          "Indrawati river",
          "Indrawati River",
          "Melamchi River",
          "Melamchi Khola"
        ],
        "opt_cutoff": 5,
        "pess_cutoff": 16,
        "unver_routes": 557,
        "buildings_destroyed": 72,
        "mtime": 1791277326.1609974
      },
      {
        "run_name": "grid_0.55_C1",
        "path": "/home/zeus/Downloads/project1/runs/grid_0.55_C1",
        "label": "आमाछोदिङ्मो / Bhote Koshi (2026-03-15)",
        "event_date": "2026-03-15",
        "bbox": [
          85.3,
          28.1,
          85.42,
          28.25
        ],
        "data_mode": "COMPLETED",
        "top_places": [
          "आमाछोदिङ्मो",
          "Aamachhodingmo",
          "ब्राबल",
          "Brabal",
          "पाजुङ",
          "Pajung"
        ],
        "top_waterways": [
          "Bhote Koshi",
          "Trishuli River",
          "Langtang Khola",
          "Chilime Khola"
        ],
        "opt_cutoff": 0,
        "pess_cutoff": 0,
        "unver_routes": 5,
        "buildings_destroyed": 0,
        "mtime": 1791276785.0517888
      },
      {
        "run_name": "grid_0.55_C2",
        "path": "/home/zeus/Downloads/project1/runs/grid_0.55_C2",
        "label": "आमाछोदिङ्मो / Bhote Koshi (2025-11-15)",
        "event_date": "2025-11-15",
        "bbox": [
          85.3,
          28.1,
          85.42,
          28.25
        ],
        "data_mode": "COMPLETED",
        "top_places": [
          "आमाछोदिङ्मो",
          "Aamachhodingmo",
          "ब्राबल",
          "Brabal",
          "पाजुङ",
          "Pajung"
        ],
        "top_waterways": [
          "Bhote Koshi",
          "Trishuli River",
          "Langtang Khola",
          "Chilime Khola"
        ],
        "opt_cutoff": 0,
        "pess_cutoff": 0,
        "unver_routes": 0,
        "buildings_destroyed": 0,
        "mtime": 1791276877.9173038
      },
      {
        "run_name": "grid_0.55_C3",
        "path": "/home/zeus/Downloads/project1/runs/grid_0.55_C3",
        "label": "आमाछोदिङ्मो / Bhote Koshi (2026-05-15)",
        "event_date": "2026-05-15",
        "bbox": [
          85.3,
          28.1,
          85.42,
          28.25
        ],
        "data_mode": "COMPLETED",
        "top_places": [
          "आमाछोदिङ्मो",
          "Aamachhodingmo",
          "ब्राबल",
          "Brabal",
          "पाजुङ",
          "Pajung"
        ],
        "top_waterways": [
          "Bhote Koshi",
          "Trishuli River",
          "Langtang Khola",
          "Chilime Khola"
        ],
        "opt_cutoff": 0,
        "pess_cutoff": 0,
        "unver_routes": 65,
        "buildings_destroyed": 0,
        "mtime": 1791276484.5948534
      },
      {
        "run_name": "grid_0.55_C4",
        "path": "/home/zeus/Downloads/project1/runs/grid_0.55_C4",
        "label": "Melamchi / Indrawati river (2021-03-15)",
        "event_date": "2021-03-15",
        "bbox": [
          85.53,
          27.8,
          85.62,
          27.95
        ],
        "data_mode": "COMPLETED",
        "top_places": [
          "Melamchi",
          "Bansbari",
          "Duwachaur",
          "Talamarang",
          "Langarche",
          "Sikharpur"
        ],
        "top_waterways": [
          "Indrawati river",
          "Melamchi River",
          "Indrawati River"
        ],
        "opt_cutoff": 0,
        "pess_cutoff": 0,
        "unver_routes": 0,
        "buildings_destroyed": 0,
        "mtime": 1791277064.7163844
      },
      {
        "run_name": "grid_0.65_A",
        "path": "/home/zeus/Downloads/project1/runs/grid_0.65_A",
        "label": "आमाछोदिङ्मो / Bhote Koshi (2026-08-26)",
        "event_date": "2026-08-26",
        "bbox": [
          85.3,
          28.1,
          85.42,
          28.25
        ],
        "data_mode": "COMPLETED",
        "top_places": [
          "आमाछोदिङ्मो",
          "Aamachhodingmo",
          "ब्राबल",
          "Brabal",
          "पाजुङ",
          "Pajung"
        ],
        "top_waterways": [
          "Bhote Koshi",
          "Trishuli River",
          "Langtang Khola",
          "Chilime Khola"
        ],
        "opt_cutoff": 44,
        "pess_cutoff": 44,
        "unver_routes": 23,
        "buildings_destroyed": 107,
        "mtime": 1791278760.6963003
      },
      {
        "run_name": "grid_0.65_B",
        "path": "/home/zeus/Downloads/project1/runs/grid_0.65_B",
        "label": "Melamchi / Indrawati river (2021-06-15)",
        "event_date": "2021-06-15",
        "bbox": [
          85.53,
          27.8,
          85.62,
          27.95
        ],
        "data_mode": "COMPLETED",
        "top_places": [
          "Melamchi",
          "Bansbari",
          "Duwachaur",
          "Talamarang",
          "Langarche",
          "Sikharpur"
        ],
        "top_waterways": [
          "Indrawati river",
          "Indrawati River",
          "Melamchi River",
          "Melamchi Khola"
        ],
        "opt_cutoff": 5,
        "pess_cutoff": 16,
        "unver_routes": 557,
        "buildings_destroyed": 72,
        "mtime": 1791279016.4663165
      },
      {
        "run_name": "grid_0.65_C1",
        "path": "/home/zeus/Downloads/project1/runs/grid_0.65_C1",
        "label": "आमाछोदिङ्मो / Bhote Koshi (2026-03-15)",
        "event_date": "2026-03-15",
        "bbox": [
          85.3,
          28.1,
          85.42,
          28.25
        ],
        "data_mode": "COMPLETED",
        "top_places": [
          "आमाछोदिङ्मो",
          "Aamachhodingmo",
          "ब्राबल",
          "Brabal",
          "पाजुङ",
          "Pajung"
        ],
        "top_waterways": [
          "Bhote Koshi",
          "Trishuli River",
          "Langtang Khola",
          "Chilime Khola"
        ],
        "opt_cutoff": 0,
        "pess_cutoff": 0,
        "unver_routes": 5,
        "buildings_destroyed": 0,
        "mtime": 1791278284.2741995
      },
      {
        "run_name": "grid_0.65_C2",
        "path": "/home/zeus/Downloads/project1/runs/grid_0.65_C2",
        "label": "आमाछोदिङ्मो / Bhote Koshi (2025-11-15)",
        "event_date": "2025-11-15",
        "bbox": [
          85.3,
          28.1,
          85.42,
          28.25
        ],
        "data_mode": "COMPLETED",
        "top_places": [
          "आमाछोदिङ्मो",
          "Aamachhodingmo",
          "ब्राबल",
          "Brabal",
          "पाजुङ",
          "Pajung"
        ],
        "top_waterways": [
          "Bhote Koshi",
          "Trishuli River",
          "Langtang Khola",
          "Chilime Khola"
        ],
        "opt_cutoff": 0,
        "pess_cutoff": 0,
        "unver_routes": 0,
        "buildings_destroyed": 0,
        "mtime": 1791278377.1662636
      },
      {
        "run_name": "grid_0.65_C3",
        "path": "/home/zeus/Downloads/project1/runs/grid_0.65_C3",
        "label": "आमाछोदिङ्मो / Bhote Koshi (2026-05-15)",
        "event_date": "2026-05-15",
        "bbox": [
          85.3,
          28.1,
          85.42,
          28.25
        ],
        "data_mode": "COMPLETED",
        "top_places": [
          "आमाछोदिङ्मो",
          "Aamachhodingmo",
          "ब्राबल",
          "Brabal",
          "पाजुङ",
          "Pajung"
        ],
        "top_waterways": [
          "Bhote Koshi",
          "Trishuli River",
          "Langtang Khola",
          "Chilime Khola"
        ],
        "opt_cutoff": 0,
        "pess_cutoff": 0,
        "unver_routes": 65,
        "buildings_destroyed": 0,
        "mtime": 1791278470.0426764
      },
      {
        "run_name": "grid_0.65_C4",
        "path": "/home/zeus/Downloads/project1/runs/grid_0.65_C4",
        "label": "Melamchi / Indrawati river (2021-03-15)",
        "event_date": "2021-03-15",
        "bbox": [
          85.53,
          27.8,
          85.62,
          27.95
        ],
        "data_mode": "COMPLETED",
        "top_places": [
          "Melamchi",
          "Bansbari",
          "Duwachaur",
          "Talamarang",
          "Langarche",
          "Sikharpur"
        ],
        "top_waterways": [
          "Indrawati river",
          "Melamchi River",
          "Indrawati River"
        ],
        "opt_cutoff": 0,
        "pess_cutoff": 0,
        "unver_routes": 0,
        "buildings_destroyed": 0,
        "mtime": 1791278642.3954332
      },
      {
        "run_name": "grid_0.6_A",
        "path": "/home/zeus/Downloads/project1/runs/grid_0.6_A",
        "label": "आमाछोदिङ्मो / Bhote Koshi (2026-08-26)",
        "event_date": "2026-08-26",
        "bbox": [
          85.3,
          28.1,
          85.42,
          28.25
        ],
        "data_mode": "COMPLETED",
        "top_places": [
          "आमाछोदिङ्मो",
          "Aamachhodingmo",
          "ब्राबल",
          "Brabal",
          "पाजुङ",
          "Pajung"
        ],
        "top_waterways": [
          "Bhote Koshi",
          "Trishuli River",
          "Langtang Khola",
          "Chilime Khola"
        ],
        "opt_cutoff": 44,
        "pess_cutoff": 44,
        "unver_routes": 23,
        "buildings_destroyed": 107,
        "mtime": 1791277909.297664
      },
      {
        "run_name": "grid_0.6_B",
        "path": "/home/zeus/Downloads/project1/runs/grid_0.6_B",
        "label": "Melamchi / Indrawati river (2021-06-15)",
        "event_date": "2021-06-15",
        "bbox": [
          85.53,
          27.8,
          85.62,
          27.95
        ],
        "data_mode": "COMPLETED",
        "top_places": [
          "Melamchi",
          "Bansbari",
          "Duwachaur",
          "Talamarang",
          "Langarche",
          "Sikharpur"
        ],
        "top_waterways": [
          "Indrawati river",
          "Indrawati River",
          "Melamchi River",
          "Melamchi Khola"
        ],
        "opt_cutoff": 5,
        "pess_cutoff": 16,
        "unver_routes": 557,
        "buildings_destroyed": 72,
        "mtime": 1791278187.9458277
      },
      {
        "run_name": "grid_0.6_C1",
        "path": "/home/zeus/Downloads/project1/runs/grid_0.6_C1",
        "label": "आमाछोदिङ्मो / Bhote Koshi (2026-03-15)",
        "event_date": "2026-03-15",
        "bbox": [
          85.3,
          28.1,
          85.42,
          28.25
        ],
        "data_mode": "COMPLETED",
        "top_places": [
          "आमाछोदिङ्मो",
          "Aamachhodingmo",
          "ब्राबल",
          "Brabal",
          "पाजुङ",
          "Pajung"
        ],
        "top_waterways": [
          "Bhote Koshi",
          "Trishuli River",
          "Langtang Khola",
          "Chilime Khola"
        ],
        "opt_cutoff": 0,
        "pess_cutoff": 0,
        "unver_routes": 5,
        "buildings_destroyed": 0,
        "mtime": 1791277421.491362
      },
      {
        "run_name": "grid_0.6_C2",
        "path": "/home/zeus/Downloads/project1/runs/grid_0.6_C2",
        "label": "आमाछोदिङ्मो / Bhote Koshi (2025-11-15)",
        "event_date": "2025-11-15",
        "bbox": [
          85.3,
          28.1,
          85.42,
          28.25
        ],
        "data_mode": "COMPLETED",
        "top_places": [
          "आमाछोदिङ्मो",
          "Aamachhodingmo",
          "ब्राबल",
          "Brabal",
          "पाजुङ",
          "Pajung"
        ],
        "top_waterways": [
          "Bhote Koshi",
          "Trishuli River",
          "Langtang Khola",
          "Chilime Khola"
        ],
        "opt_cutoff": 0,
        "pess_cutoff": 0,
        "unver_routes": 0,
        "buildings_destroyed": 0,
        "mtime": 1791277511.72287
      },
      {
        "run_name": "grid_0.6_C3",
        "path": "/home/zeus/Downloads/project1/runs/grid_0.6_C3",
        "label": "आमाछोदिङ्मो / Bhote Koshi (2026-05-15)",
        "event_date": "2026-05-15",
        "bbox": [
          85.3,
          28.1,
          85.42,
          28.25
        ],
        "data_mode": "COMPLETED",
        "top_places": [
          "आमाछोदिङ्मो",
          "Aamachhodingmo",
          "ब्राबल",
          "Brabal",
          "पाजुङ",
          "Pajung"
        ],
        "top_waterways": [
          "Bhote Koshi",
          "Trishuli River",
          "Langtang Khola",
          "Chilime Khola"
        ],
        "opt_cutoff": 0,
        "pess_cutoff": 0,
        "unver_routes": 65,
        "buildings_destroyed": 0,
        "mtime": 1791277601.7270834
      },
      {
        "run_name": "grid_0.6_C4",
        "path": "/home/zeus/Downloads/project1/runs/grid_0.6_C4",
        "label": "Melamchi / Indrawati river (2021-03-15)",
        "event_date": "2021-03-15",
        "bbox": [
          85.53,
          27.8,
          85.62,
          27.95
        ],
        "data_mode": "COMPLETED",
        "top_places": [
          "Melamchi",
          "Bansbari",
          "Duwachaur",
          "Talamarang",
          "Langarche",
          "Sikharpur"
        ],
        "top_waterways": [
          "Indrawati river",
          "Melamchi River",
          "Indrawati River"
        ],
        "opt_cutoff": 0,
        "pess_cutoff": 0,
        "unver_routes": 0,
        "buildings_destroyed": 0,
        "mtime": 1791277783.8121767
      },
      {
        "run_name": "grid_none_A",
        "path": "/home/zeus/Downloads/project1/runs/grid_none_A",
        "label": "आमाछोदिङ्मो / Bhote Koshi (2026-08-26)",
        "event_date": "2026-08-26",
        "bbox": [
          85.3,
          28.1,
          85.42,
          28.25
        ],
        "data_mode": "COMPLETED",
        "top_places": [
          "आमाछोदिङ्मो",
          "Aamachhodingmo",
          "ब्राबल",
          "Brabal",
          "पाजुङ",
          "Pajung"
        ],
        "top_waterways": [
          "Bhote Koshi",
          "Trishuli River",
          "Langtang Khola",
          "Chilime Khola"
        ],
        "opt_cutoff": 44,
        "pess_cutoff": 44,
        "unver_routes": 23,
        "buildings_destroyed": 107,
        "mtime": 1791279649.0161548
      },
      {
        "run_name": "grid_none_B",
        "path": "/home/zeus/Downloads/project1/runs/grid_none_B",
        "label": "Melamchi / Indrawati river (2021-06-15)",
        "event_date": "2021-06-15",
        "bbox": [
          85.53,
          27.8,
          85.62,
          27.95
        ],
        "data_mode": "COMPLETED",
        "top_places": [
          "Melamchi",
          "Bansbari",
          "Duwachaur",
          "Talamarang",
          "Langarche",
          "Sikharpur"
        ],
        "top_waterways": [
          "Indrawati river",
          "Indrawati River",
          "Melamchi River",
          "Melamchi Khola"
        ],
        "opt_cutoff": 5,
        "pess_cutoff": 15,
        "unver_routes": 557,
        "buildings_destroyed": 69,
        "mtime": 1791279948.5013325
      },
      {
        "run_name": "grid_none_C1",
        "path": "/home/zeus/Downloads/project1/runs/grid_none_C1",
        "label": "आमाछोदिङ्मो / Bhote Koshi (2026-03-15)",
        "event_date": "2026-03-15",
        "bbox": [
          85.3,
          28.1,
          85.42,
          28.25
        ],
        "data_mode": "COMPLETED",
        "top_places": [
          "आमाछोदिङ्मो",
          "Aamachhodingmo",
          "ब्राबल",
          "Brabal",
          "पाजुङ",
          "Pajung"
        ],
        "top_waterways": [
          "Bhote Koshi",
          "Trishuli River",
          "Langtang Khola",
          "Chilime Khola"
        ],
        "opt_cutoff": 0,
        "pess_cutoff": 0,
        "unver_routes": 5,
        "buildings_destroyed": 0,
        "mtime": 1791279111.8427298
      },
      {
        "run_name": "grid_none_C2",
        "path": "/home/zeus/Downloads/project1/runs/grid_none_C2",
        "label": "आमाछोदिङ्मो / Bhote Koshi (2025-11-15)",
        "event_date": "2025-11-15",
        "bbox": [
          85.3,
          28.1,
          85.42,
          28.25
        ],
        "data_mode": "COMPLETED",
        "top_places": [
          "आमाछोदिङ्मो",
          "Aamachhodingmo",
          "ब्राबल",
          "Brabal",
          "पाजुङ",
          "Pajung"
        ],
        "top_waterways": [
          "Bhote Koshi",
          "Trishuli River",
          "Langtang Khola",
          "Chilime Khola"
        ],
        "opt_cutoff": 0,
        "pess_cutoff": 0,
        "unver_routes": 0,
        "buildings_destroyed": 0,
        "mtime": 1791279201.683845
      },
      {
        "run_name": "grid_none_C3",
        "path": "/home/zeus/Downloads/project1/runs/grid_none_C3",
        "label": "आमाछोदिङ्मो / Bhote Koshi (2026-05-15)",
        "event_date": "2026-05-15",
        "bbox": [
          85.3,
          28.1,
          85.42,
          28.25
        ],
        "data_mode": "COMPLETED",
        "top_places": [
          "आमाछोदिङ्मो",
          "Aamachhodingmo",
          "ब्राबल",
          "Brabal",
          "पाजुङ",
          "Pajung"
        ],
        "top_waterways": [
          "Bhote Koshi",
          "Trishuli River",
          "Langtang Khola",
          "Chilime Khola"
        ],
        "opt_cutoff": 0,
        "pess_cutoff": 0,
        "unver_routes": 65,
        "buildings_destroyed": 0,
        "mtime": 1791279305.4243968
      },
      {
        "run_name": "grid_none_C4",
        "path": "/home/zeus/Downloads/project1/runs/grid_none_C4",
        "label": "Melamchi / Indrawati river (2021-03-15)",
        "event_date": "2021-03-15",
        "bbox": [
          85.53,
          27.8,
          85.62,
          27.95
        ],
        "data_mode": "COMPLETED",
        "top_places": [
          "Melamchi",
          "Bansbari",
          "Duwachaur",
          "Talamarang",
          "Langarche",
          "Sikharpur"
        ],
        "top_waterways": [
          "Indrawati river",
          "Melamchi River",
          "Indrawati River"
        ],
        "opt_cutoff": 0,
        "pess_cutoff": 0,
        "unver_routes": 0,
        "buildings_destroyed": 0,
        "mtime": 1791279521.949023
      },
      {
        "run_name": "practice_assam_event",
        "path": "/home/zeus/Downloads/project1/runs/practice_assam_event",
        "label": "Silghat (2024-07-02)",
        "event_date": "2024-07-02",
        "bbox": [
          92.85,
          26.55,
          93.1,
          26.75
        ],
        "data_mode": "COMPLETED",
        "top_places": [
          "Silghat",
          "Panpur",
          "Jamugurihat",
          "Chutia",
          "Kuwarital"
        ],
        "top_waterways": [],
        "opt_cutoff": 9,
        "pess_cutoff": 9,
        "unver_routes": 0,
        "buildings_destroyed": 0,
        "mtime": 1791307682.3177984
      },
      {
        "run_name": "practice_assam_noevent",
        "path": "/home/zeus/Downloads/project1/runs/practice_assam_noevent",
        "label": "Silghat (2024-01-15)",
        "event_date": "2024-01-15",
        "bbox": [
          92.85,
          26.55,
          93.1,
          26.75
        ],
        "data_mode": "DEGRADED",
        "top_places": [
          "Silghat",
          "Panpur",
          "Jamugurihat",
          "Chutia",
          "Kuwarital"
        ],
        "top_waterways": [],
        "opt_cutoff": 0,
        "pess_cutoff": 0,
        "unver_routes": 0,
        "buildings_destroyed": 0,
        "mtime": 1791308063.7364616
      },
      {
        "run_name": "practice_sikkim_event",
        "path": "/home/zeus/Downloads/project1/runs/practice_sikkim_event",
        "label": "Nanga (2023-10-04)",
        "event_date": "2023-10-04",
        "bbox": [
          88.58,
          27.53,
          88.72,
          27.67
        ],
        "data_mode": "COMPLETED",
        "top_places": [
          "Nanga"
        ],
        "top_waterways": [],
        "opt_cutoff": 26,
        "pess_cutoff": 27,
        "unver_routes": 2,
        "buildings_destroyed": 47,
        "mtime": 1791287497.707879
      },
      {
        "run_name": "practice_sikkim_noevent",
        "path": "/home/zeus/Downloads/project1/runs/practice_sikkim_noevent",
        "label": "Nanga (2023-04-15)",
        "event_date": "2023-04-15",
        "bbox": [
          88.58,
          27.53,
          88.72,
          27.67
        ],
        "data_mode": "COMPLETED",
        "top_places": [
          "Nanga"
        ],
        "top_waterways": [],
        "opt_cutoff": 0,
        "pess_cutoff": 0,
        "unver_routes": 0,
        "buildings_destroyed": 0,
        "mtime": 1791287904.0581877
      },
      {
        "run_name": "run_A_cold_1",
        "path": "/home/zeus/Downloads/project1/runs/run_A_cold_1",
        "label": "आमाछोदिङ्मो / Bhote Koshi (2026-08-26)",
        "event_date": "2026-08-26",
        "bbox": [
          85.3,
          28.1,
          85.42,
          28.25
        ],
        "data_mode": "COMPLETED",
        "top_places": [
          "आमाछोदिङ्मो",
          "Aamachhodingmo",
          "ब्राबल",
          "Brabal",
          "पाजुङ",
          "Pajung"
        ],
        "top_waterways": [
          "Bhote Koshi",
          "Trishuli River",
          "Langtang Khola",
          "Chilime Khola"
        ],
        "opt_cutoff": 44,
        "pess_cutoff": 44,
        "unver_routes": 23,
        "buildings_destroyed": 84,
        "mtime": 1791261112.079089
      },
      {
        "run_name": "test_A_check_tmp",
        "path": "/home/zeus/Downloads/project1/runs/test_A_check_tmp",
        "label": "आमाछोदिङ्मो / Bhote Koshi (2026-08-26)",
        "event_date": "2026-08-26",
        "bbox": [
          85.3,
          28.1,
          85.42,
          28.25
        ],
        "data_mode": "COMPLETED",
        "top_places": [
          "आमाछोदिङ्मो",
          "Aamachhodingmo",
          "ब्राबल",
          "Brabal",
          "पाजुङ",
          "Pajung"
        ],
        "top_waterways": [
          "Bhote Koshi",
          "Trishuli River",
          "Langtang Khola",
          "Chilime Khola"
        ],
        "opt_cutoff": 44,
        "pess_cutoff": 44,
        "unver_routes": 23,
        "buildings_destroyed": 107,
        "mtime": 1791308888.500412
      },
      {
        "run_name": "test_A_cold",
        "path": "/home/zeus/Downloads/project1/runs/test_A_cold",
        "label": "ब्राबल / Trishuli River (2026-08-26)",
        "event_date": "2026-08-26",
        "bbox": [
          85.3,
          28.1,
          85.42,
          28.25
        ],
        "data_mode": "COMPLETED",
        "top_places": [
          "ब्राबल",
          "Brabal",
          "आमाछोदिङ्मो",
          "Aamachhodingmo",
          "बाहुनडाँडा",
          "Bahun Danda"
        ],
        "top_waterways": [
          "Trishuli River",
          "Bhote Koshi",
          "Langtang Khola",
          "Chilime Khola"
        ],
        "opt_cutoff": 44,
        "pess_cutoff": 44,
        "unver_routes": 23,
        "buildings_destroyed": 106,
        "mtime": 1791134743.5059748
      },
      {
        "run_name": "test_A_cold_final2_run1",
        "path": "/home/zeus/Downloads/project1/runs/test_A_cold_final2_run1",
        "label": "आमाछोदिङ्मो / Bhote Koshi (2026-08-26)",
        "event_date": "2026-08-26",
        "bbox": [
          85.3,
          28.1,
          85.42,
          28.25
        ],
        "data_mode": "COMPLETED",
        "top_places": [
          "आमाछोदिङ्मो",
          "Aamachhodingmo",
          "ब्राबल",
          "Brabal",
          "पाजुङ",
          "Pajung"
        ],
        "top_waterways": [
          "Bhote Koshi",
          "Trishuli River",
          "Langtang Khola",
          "Chilime Khola"
        ],
        "opt_cutoff": 44,
        "pess_cutoff": 44,
        "unver_routes": 23,
        "buildings_destroyed": 107,
        "mtime": 1791282614.0902503
      },
      {
        "run_name": "test_A_cold_final2_run2",
        "path": "/home/zeus/Downloads/project1/runs/test_A_cold_final2_run2",
        "label": "आमाछोदिङ्मो / Bhote Koshi (2026-08-26)",
        "event_date": "2026-08-26",
        "bbox": [
          85.3,
          28.1,
          85.42,
          28.25
        ],
        "data_mode": "COMPLETED",
        "top_places": [
          "आमाछोदिङ्मो",
          "Aamachhodingmo",
          "ब्राबल",
          "Brabal",
          "पाजुङ",
          "Pajung"
        ],
        "top_waterways": [
          "Bhote Koshi",
          "Trishuli River",
          "Langtang Khola",
          "Chilime Khola"
        ],
        "opt_cutoff": 44,
        "pess_cutoff": 44,
        "unver_routes": 23,
        "buildings_destroyed": 107,
        "mtime": 1791283300.29172
      },
      {
        "run_name": "test_A_cold_final_run1",
        "path": "/home/zeus/Downloads/project1/runs/test_A_cold_final_run1",
        "label": "आमाछोदिङ्मो / Bhote Koshi (2026-08-26)",
        "event_date": "2026-08-26",
        "bbox": [
          85.3,
          28.1,
          85.42,
          28.25
        ],
        "data_mode": "COMPLETED",
        "top_places": [
          "आमाछोदिङ्मो",
          "Aamachhodingmo",
          "ब्राबल",
          "Brabal",
          "पाजुङ",
          "Pajung"
        ],
        "top_waterways": [
          "Bhote Koshi",
          "Trishuli River",
          "Langtang Khola",
          "Chilime Khola"
        ],
        "opt_cutoff": 44,
        "pess_cutoff": 44,
        "unver_routes": 23,
        "buildings_destroyed": 107,
        "mtime": 1791271742.6321156
      },
      {
        "run_name": "test_A_cold_final_run2",
        "path": "/home/zeus/Downloads/project1/runs/test_A_cold_final_run2",
        "label": "आमाछोदिङ्मो / Bhote Koshi (2026-08-26)",
        "event_date": "2026-08-26",
        "bbox": [
          85.3,
          28.1,
          85.42,
          28.25
        ],
        "data_mode": "COMPLETED",
        "top_places": [
          "आमाछोदिङ्मो",
          "Aamachhodingmo",
          "ब्राबल",
          "Brabal",
          "पाजुङ",
          "Pajung"
        ],
        "top_waterways": [
          "Bhote Koshi",
          "Trishuli River",
          "Langtang Khola",
          "Chilime Khola"
        ],
        "opt_cutoff": 44,
        "pess_cutoff": 44,
        "unver_routes": 23,
        "buildings_destroyed": 107,
        "mtime": 1791272058.8918204
      },
      {
        "run_name": "test_A_cold_run1",
        "path": "/home/zeus/Downloads/project1/runs/test_A_cold_run1",
        "label": "आमाछोदिङ्मो / Bhote Koshi (2026-08-26)",
        "event_date": "2026-08-26",
        "bbox": [
          85.3,
          28.1,
          85.42,
          28.25
        ],
        "data_mode": "COMPLETED",
        "top_places": [
          "आमाछोदिङ्मो",
          "Aamachhodingmo",
          "ब्राबल",
          "Brabal",
          "पाजुङ",
          "Pajung"
        ],
        "top_waterways": [
          "Bhote Koshi",
          "Trishuli River",
          "Langtang Khola",
          "Chilime Khola"
        ],
        "opt_cutoff": 44,
        "pess_cutoff": 44,
        "unver_routes": 23,
        "buildings_destroyed": 107,
        "mtime": 1791262611.717568
      },
      {
        "run_name": "test_A_cold_run2",
        "path": "/home/zeus/Downloads/project1/runs/test_A_cold_run2",
        "label": "आमाछोदिङ्मो / Bhote Koshi (2026-08-26)",
        "event_date": "2026-08-26",
        "bbox": [
          85.3,
          28.1,
          85.42,
          28.25
        ],
        "data_mode": "COMPLETED",
        "top_places": [
          "आमाछोदिङ्मो",
          "Aamachhodingmo",
          "ब्राबल",
          "Brabal",
          "पाजुङ",
          "Pajung"
        ],
        "top_waterways": [
          "Bhote Koshi",
          "Trishuli River",
          "Langtang Khola",
          "Chilime Khola"
        ],
        "opt_cutoff": 44,
        "pess_cutoff": 44,
        "unver_routes": 23,
        "buildings_destroyed": 107,
        "mtime": 1791262853.3912888
      },
      {
        "run_name": "test_A_cold_v4",
        "path": "/home/zeus/Downloads/project1/runs/test_A_cold_v4",
        "label": "ब्राबल / Trishuli River (2026-08-26)",
        "event_date": "2026-08-26",
        "bbox": [
          85.3,
          28.1,
          85.42,
          28.25
        ],
        "data_mode": "COMPLETED",
        "top_places": [
          "ब्राबल",
          "Brabal",
          "आमाछोदिङ्मो",
          "Aamachhodingmo",
          "बाहुनडाँडा",
          "Bahun Danda"
        ],
        "top_waterways": [
          "Trishuli River",
          "Bhote Koshi",
          "Langtang Khola",
          "Chilime Khola"
        ],
        "opt_cutoff": 44,
        "pess_cutoff": 44,
        "unver_routes": 23,
        "buildings_destroyed": 102,
        "mtime": 1791196832.6899426
      },
      {
        "run_name": "test_A_cold_verify",
        "path": "/home/zeus/Downloads/project1/runs/test_A_cold_verify",
        "label": "आमाछोदिङ्मो / Bhote Koshi",
        "event_date": "unknown",
        "bbox": null,
        "data_mode": "COMPLETED",
        "top_places": [
          "आमाछोदिङ्मो",
          "Aamachhodingmo",
          "ब्राबल",
          "Brabal",
          "पाजुङ",
          "Pajung"
        ],
        "top_waterways": [
          "Bhote Koshi",
          "Trishuli River",
          "Langtang Khola",
          "Chilime Khola"
        ],
        "opt_cutoff": null,
        "pess_cutoff": null,
        "unver_routes": null,
        "buildings_destroyed": 0,
        "mtime": 1791285047.534749
      },
      {
        "run_name": "test_A_crs_check",
        "path": "/home/zeus/Downloads/project1/runs/test_A_crs_check",
        "label": "आमाछोदिङ्मो / Bhote Koshi (2026-08-26)",
        "event_date": "2026-08-26",
        "bbox": [
          85.3,
          28.1,
          85.42,
          28.25
        ],
        "data_mode": "COMPLETED",
        "top_places": [
          "आमाछोदिङ्मो",
          "Aamachhodingmo",
          "ब्राबल",
          "Brabal",
          "पाजुङ",
          "Pajung"
        ],
        "top_waterways": [
          "Bhote Koshi",
          "Trishuli River",
          "Langtang Khola",
          "Chilime Khola"
        ],
        "opt_cutoff": 44,
        "pess_cutoff": 44,
        "unver_routes": 23,
        "buildings_destroyed": 107,
        "mtime": 1791285988.2694957
      },
      {
        "run_name": "test_A_crs_verify",
        "path": "/home/zeus/Downloads/project1/runs/test_A_crs_verify",
        "label": "ब्राबल / Trishuli River (2026-08-26)",
        "event_date": "2026-08-26",
        "bbox": [
          85.3,
          28.1,
          85.42,
          28.25
        ],
        "data_mode": "COMPLETED",
        "top_places": [
          "ब्राबल",
          "Brabal",
          "आमाछोदिङ्मो",
          "Aamachhodingmo",
          "बाहुनडाँडा",
          "Bahun Danda"
        ],
        "top_waterways": [
          "Trishuli River",
          "Bhote Koshi",
          "Langtang Khola",
          "Chilime Khola"
        ],
        "opt_cutoff": 44,
        "pess_cutoff": 44,
        "unver_routes": 23,
        "buildings_destroyed": 81,
        "mtime": 1791284802.2883484
      },
      {
        "run_name": "test_A_e2e_v5",
        "path": "/home/zeus/Downloads/project1/runs/test_A_e2e_v5",
        "label": "ब्राबल / Trishuli River (2026-08-26)",
        "event_date": "2026-08-26",
        "bbox": [
          85.3,
          28.1,
          85.42,
          28.25
        ],
        "data_mode": "COMPLETED",
        "top_places": [
          "ब्राबल",
          "Brabal",
          "आमाछोदिङ्मो",
          "Aamachhodingmo",
          "बाहुनडाँडा",
          "Bahun Danda"
        ],
        "top_waterways": [
          "Trishuli River",
          "Bhote Koshi",
          "Langtang Khola",
          "Chilime Khola"
        ],
        "opt_cutoff": 44,
        "pess_cutoff": 44,
        "unver_routes": 23,
        "buildings_destroyed": 81,
        "mtime": 1791200253.5362628
      },
      {
        "run_name": "test_A_e2e_v7",
        "path": "/home/zeus/Downloads/project1/runs/test_A_e2e_v7",
        "label": "ब्राबल / Trishuli River (2026-08-26)",
        "event_date": "2026-08-26",
        "bbox": [
          85.3,
          28.1,
          85.42,
          28.25
        ],
        "data_mode": "COMPLETED",
        "top_places": [
          "ब्राबल",
          "Brabal",
          "आमाछोदिङ्मो",
          "Aamachhodingmo",
          "बाहुनडाँडा",
          "Bahun Danda"
        ],
        "top_waterways": [
          "Trishuli River",
          "Bhote Koshi",
          "Langtang Khola",
          "Chilime Khola"
        ],
        "opt_cutoff": 44,
        "pess_cutoff": 44,
        "unver_routes": 23,
        "buildings_destroyed": 81,
        "mtime": 1791220695.1926057
      },
      {
        "run_name": "test_A_trishuli",
        "path": "/home/zeus/Downloads/project1/runs/test_A_trishuli",
        "label": "ब्राबल / Trishuli River (2026-08-26)",
        "event_date": "2026-08-26",
        "bbox": [
          85.3,
          28.1,
          85.42,
          28.25
        ],
        "data_mode": "COMPLETED",
        "top_places": [
          "ब्राबल",
          "Brabal",
          "आमाछोदिङ्मो",
          "Aamachhodingmo",
          "बाहुनडाँडा",
          "Bahun Danda"
        ],
        "top_waterways": [
          "Trishuli River",
          "Bhote Koshi",
          "Langtang Khola",
          "Chilime Khola"
        ],
        "opt_cutoff": 44,
        "pess_cutoff": 44,
        "unver_routes": 23,
        "buildings_destroyed": 81,
        "mtime": 1791193596.4509783
      },
      {
        "run_name": "test_A_verify_mod",
        "path": "/home/zeus/Downloads/project1/runs/test_A_verify_mod",
        "label": "test_A_verify_mod",
        "event_date": "unknown",
        "bbox": null,
        "data_mode": "COMPLETED",
        "top_places": [],
        "top_waterways": [],
        "opt_cutoff": null,
        "pess_cutoff": null,
        "unver_routes": null,
        "buildings_destroyed": 0,
        "mtime": 1791308542.1865323
      },
      {
        "run_name": "test_B_check_tmp",
        "path": "/home/zeus/Downloads/project1/runs/test_B_check_tmp",
        "label": "Melamchi / Indrawati river (2021-06-15)",
        "event_date": "2021-06-15",
        "bbox": [
          85.53,
          27.8,
          85.62,
          27.95
        ],
        "data_mode": "COMPLETED",
        "top_places": [
          "Melamchi",
          "Bansbari",
          "Duwachaur",
          "Talamarang",
          "Langarche",
          "Sikharpur"
        ],
        "top_waterways": [
          "Indrawati river",
          "Indrawati River",
          "Melamchi River",
          "Melamchi Khola"
        ],
        "opt_cutoff": 5,
        "pess_cutoff": 16,
        "unver_routes": 557,
        "buildings_destroyed": 69,
        "mtime": 1791309192.8105488
      },
      {
        "run_name": "test_B_cold",
        "path": "/home/zeus/Downloads/project1/runs/test_B_cold",
        "label": "Melamchi / Indrawati river (2021-06-15)",
        "event_date": "2021-06-15",
        "bbox": [
          85.53,
          27.8,
          85.62,
          27.95
        ],
        "data_mode": "COMPLETED",
        "top_places": [
          "Melamchi",
          "Bansbari",
          "Duwachaur",
          "Talamarang",
          "Langarche",
          "Sikharpur"
        ],
        "top_waterways": [
          "Indrawati river",
          "Indrawati River",
          "Melamchi River",
          "Melamchi Khola"
        ],
        "opt_cutoff": 6,
        "pess_cutoff": 37,
        "unver_routes": 578,
        "buildings_destroyed": 88,
        "mtime": 1791264013.1900635
      },
      {
        "run_name": "test_B_cold_final",
        "path": "/home/zeus/Downloads/project1/runs/test_B_cold_final",
        "label": "Melamchi / Indrawati river (2021-06-15)",
        "event_date": "2021-06-15",
        "bbox": [
          85.53,
          27.8,
          85.62,
          27.95
        ],
        "data_mode": "COMPLETED",
        "top_places": [
          "Melamchi",
          "Bansbari",
          "Duwachaur",
          "Talamarang",
          "Langarche",
          "Sikharpur"
        ],
        "top_waterways": [
          "Indrawati river",
          "Indrawati River",
          "Melamchi River",
          "Melamchi Khola"
        ],
        "opt_cutoff": 5,
        "pess_cutoff": 15,
        "unver_routes": 557,
        "buildings_destroyed": 69,
        "mtime": 1791272605.7730997
      },
      {
        "run_name": "test_B_cold_run1",
        "path": "/home/zeus/Downloads/project1/runs/test_B_cold_run1",
        "label": "Melamchi / Indrawati river (2021-06-15)",
        "event_date": "2021-06-15",
        "bbox": [
          85.53,
          27.8,
          85.62,
          27.95
        ],
        "data_mode": "COMPLETED",
        "top_places": [
          "Melamchi",
          "Bansbari",
          "Duwachaur",
          "Talamarang",
          "Langarche",
          "Sikharpur"
        ],
        "top_waterways": [
          "Indrawati river",
          "Indrawati River",
          "Melamchi River",
          "Melamchi Khola"
        ],
        "opt_cutoff": 0,
        "pess_cutoff": 0,
        "unver_routes": 607,
        "buildings_destroyed": 0,
        "mtime": 1791233463.8446796
      },
      {
        "run_name": "test_B_cold_run2",
        "path": "/home/zeus/Downloads/project1/runs/test_B_cold_run2",
        "label": "Melamchi / Indrawati river (2021-06-15)",
        "event_date": "2021-06-15",
        "bbox": [
          85.53,
          27.8,
          85.62,
          27.95
        ],
        "data_mode": "COMPLETED",
        "top_places": [
          "Melamchi",
          "Bansbari",
          "Duwachaur",
          "Talamarang",
          "Langarche",
          "Sikharpur"
        ],
        "top_waterways": [
          "Indrawati river",
          "Indrawati River",
          "Melamchi River",
          "Melamchi Khola"
        ],
        "opt_cutoff": 0,
        "pess_cutoff": 0,
        "unver_routes": 607,
        "buildings_destroyed": 0,
        "mtime": 1791233781.1525884
      },
      {
        "run_name": "test_B_e2e_v5",
        "path": "/home/zeus/Downloads/project1/runs/test_B_e2e_v5",
        "label": "Melamchi / Indrawati river (2021-06-15)",
        "event_date": "2021-06-15",
        "bbox": [
          85.53,
          27.8,
          85.62,
          27.95
        ],
        "data_mode": "COMPLETED",
        "top_places": [
          "Melamchi",
          "Bansbari",
          "Duwachaur",
          "Talamarang",
          "Langarche",
          "Sikharpur"
        ],
        "top_waterways": [
          "Indrawati river",
          "Indrawati River",
          "Melamchi Khola",
          "Melamchi River"
        ],
        "opt_cutoff": 10,
        "pess_cutoff": 37,
        "unver_routes": 517,
        "buildings_destroyed": 86,
        "mtime": 1791200708.7102897
      },
      {
        "run_name": "test_B_melamchi",
        "path": "/home/zeus/Downloads/project1/runs/test_B_melamchi",
        "label": "Melamchi / Indrawati river (2021-06-15)",
        "event_date": "2021-06-15",
        "bbox": [
          85.53,
          27.8,
          85.62,
          27.95
        ],
        "data_mode": "COMPLETED",
        "top_places": [
          "Melamchi",
          "Bansbari",
          "Duwachaur",
          "Talamarang",
          "Langarche",
          "Sikharpur"
        ],
        "top_waterways": [
          "Indrawati river",
          "Indrawati River",
          "Melamchi Khola",
          "Melamchi River"
        ],
        "opt_cutoff": 10,
        "pess_cutoff": 37,
        "unver_routes": 517,
        "buildings_destroyed": 86,
        "mtime": 1791193905.8619254
      },
      {
        "run_name": "test_C1_cold",
        "path": "/home/zeus/Downloads/project1/runs/test_C1_cold",
        "label": "आमाछोदिङ्मो / Bhote Koshi (2026-03-15)",
        "event_date": "2026-03-15",
        "bbox": [
          85.3,
          28.1,
          85.42,
          28.25
        ],
        "data_mode": "COMPLETED",
        "top_places": [
          "आमाछोदिङ्मो",
          "Aamachhodingmo",
          "ब्राबल",
          "Brabal",
          "पाजुङ",
          "Pajung"
        ],
        "top_waterways": [
          "Bhote Koshi",
          "Trishuli River",
          "Langtang Khola",
          "Chilime Khola"
        ],
        "opt_cutoff": 0,
        "pess_cutoff": 0,
        "unver_routes": 5,
        "buildings_destroyed": 0,
        "mtime": 1791264231.7062628
      },
      {
        "run_name": "test_C1_cold_final",
        "path": "/home/zeus/Downloads/project1/runs/test_C1_cold_final",
        "label": "आमाछोदिङ्मो / Bhote Koshi (2026-03-15)",
        "event_date": "2026-03-15",
        "bbox": [
          85.3,
          28.1,
          85.42,
          28.25
        ],
        "data_mode": "COMPLETED",
        "top_places": [
          "आमाछोदिङ्मो",
          "Aamachhodingmo",
          "ब्राबल",
          "Brabal",
          "पाजुङ",
          "Pajung"
        ],
        "top_waterways": [
          "Bhote Koshi",
          "Trishuli River",
          "Langtang Khola",
          "Chilime Khola"
        ],
        "opt_cutoff": 0,
        "pess_cutoff": 0,
        "unver_routes": 5,
        "buildings_destroyed": 0,
        "mtime": 1791272824.5599189
      },
      {
        "run_name": "test_C1_cold_run1",
        "path": "/home/zeus/Downloads/project1/runs/test_C1_cold_run1",
        "label": "आमाछोदिङ्मो / Bhote Koshi (2026-03-15)",
        "event_date": "2026-03-15",
        "bbox": [
          85.3,
          28.1,
          85.42,
          28.25
        ],
        "data_mode": "COMPLETED",
        "top_places": [
          "आमाछोदिङ्मो",
          "Aamachhodingmo",
          "ब्राबल",
          "Brabal",
          "पाजुङ",
          "Pajung"
        ],
        "top_waterways": [
          "Bhote Koshi",
          "Trishuli River",
          "Langtang Khola",
          "Chilime Khola"
        ],
        "opt_cutoff": 0,
        "pess_cutoff": 0,
        "unver_routes": 67,
        "buildings_destroyed": 0,
        "mtime": 1791233971.3627422
      },
      {
        "run_name": "test_C1_cold_run2",
        "path": "/home/zeus/Downloads/project1/runs/test_C1_cold_run2",
        "label": "आमाछोदिङ्मो / Bhote Koshi (2026-03-15)",
        "event_date": "2026-03-15",
        "bbox": [
          85.3,
          28.1,
          85.42,
          28.25
        ],
        "data_mode": "COMPLETED",
        "top_places": [
          "आमाछोदिङ्मो",
          "Aamachhodingmo",
          "ब्राबल",
          "Brabal",
          "पाजुङ",
          "Pajung"
        ],
        "top_waterways": [
          "Bhote Koshi",
          "Trishuli River",
          "Langtang Khola",
          "Chilime Khola"
        ],
        "opt_cutoff": 0,
        "pess_cutoff": 0,
        "unver_routes": 67,
        "buildings_destroyed": 0,
        "mtime": 1791234154.7042623
      },
      {
        "run_name": "test_C1_e2e_v5",
        "path": "/home/zeus/Downloads/project1/runs/test_C1_e2e_v5",
        "label": "ब्राबल / Trishuli River (2026-03-15)",
        "event_date": "2026-03-15",
        "bbox": [
          85.3,
          28.1,
          85.42,
          28.25
        ],
        "data_mode": "COMPLETED",
        "top_places": [
          "ब्राबल",
          "Brabal",
          "आमाछोदिङ्मो",
          "Aamachhodingmo",
          "बाहुनडाँडा",
          "Bahun Danda"
        ],
        "top_waterways": [
          "Trishuli River",
          "Bhote Koshi",
          "Langtang Khola",
          "Chilime Khola"
        ],
        "opt_cutoff": 0,
        "pess_cutoff": 0,
        "unver_routes": 44,
        "buildings_destroyed": 0,
        "mtime": 1791200949.0816905
      },
      {
        "run_name": "test_C2_cold",
        "path": "/home/zeus/Downloads/project1/runs/test_C2_cold",
        "label": "आमाछोदिङ्मो / Bhote Koshi (2025-11-15)",
        "event_date": "2025-11-15",
        "bbox": [
          85.3,
          28.1,
          85.42,
          28.25
        ],
        "data_mode": "COMPLETED",
        "top_places": [
          "आमाछोदिङ्मो",
          "Aamachhodingmo",
          "ब्राबल",
          "Brabal",
          "पाजुङ",
          "Pajung"
        ],
        "top_waterways": [
          "Bhote Koshi",
          "Trishuli River",
          "Langtang Khola",
          "Chilime Khola"
        ],
        "opt_cutoff": 0,
        "pess_cutoff": 0,
        "unver_routes": 0,
        "buildings_destroyed": 0,
        "mtime": 1791264427.704781
      },
      {
        "run_name": "test_C2_cold_final",
        "path": "/home/zeus/Downloads/project1/runs/test_C2_cold_final",
        "label": "आमाछोदिङ्मो / Bhote Koshi (2025-11-15)",
        "event_date": "2025-11-15",
        "bbox": [
          85.3,
          28.1,
          85.42,
          28.25
        ],
        "data_mode": "COMPLETED",
        "top_places": [
          "आमाछोदिङ्मो",
          "Aamachhodingmo",
          "ब्राबल",
          "Brabal",
          "पाजुङ",
          "Pajung"
        ],
        "top_waterways": [
          "Bhote Koshi",
          "Trishuli River",
          "Langtang Khola",
          "Chilime Khola"
        ],
        "opt_cutoff": 0,
        "pess_cutoff": 0,
        "unver_routes": 0,
        "buildings_destroyed": 0,
        "mtime": 1791273021.275574
      },
      {
        "run_name": "test_C2_cold_run1",
        "path": "/home/zeus/Downloads/project1/runs/test_C2_cold_run1",
        "label": "आमाछोदिङ्मो / Bhote Koshi (2025-11-15)",
        "event_date": "2025-11-15",
        "bbox": [
          85.3,
          28.1,
          85.42,
          28.25
        ],
        "data_mode": "COMPLETED",
        "top_places": [
          "आमाछोदिङ्मो",
          "Aamachhodingmo",
          "ब्राबल",
          "Brabal",
          "पाजुङ",
          "Pajung"
        ],
        "top_waterways": [
          "Bhote Koshi",
          "Trishuli River",
          "Langtang Khola",
          "Chilime Khola"
        ],
        "opt_cutoff": 0,
        "pess_cutoff": 0,
        "unver_routes": 4,
        "buildings_destroyed": 0,
        "mtime": 1791234441.5433767
      },
      {
        "run_name": "test_C2_cold_run2",
        "path": "/home/zeus/Downloads/project1/runs/test_C2_cold_run2",
        "label": "आमाछोदिङ्मो / Bhote Koshi (2025-11-15)",
        "event_date": "2025-11-15",
        "bbox": [
          85.3,
          28.1,
          85.42,
          28.25
        ],
        "data_mode": "COMPLETED",
        "top_places": [
          "आमाछोदिङ्मो",
          "Aamachhodingmo",
          "ब्राबल",
          "Brabal",
          "पाजुङ",
          "Pajung"
        ],
        "top_waterways": [
          "Bhote Koshi",
          "Trishuli River",
          "Langtang Khola",
          "Chilime Khola"
        ],
        "opt_cutoff": 0,
        "pess_cutoff": 0,
        "unver_routes": 4,
        "buildings_destroyed": 0,
        "mtime": 1791234649.7232864
      },
      {
        "run_name": "test_C2_trishuli_20251115",
        "path": "/home/zeus/Downloads/project1/runs/test_C2_trishuli_20251115",
        "label": "ब्राबल / Trishuli River",
        "event_date": "unknown",
        "bbox": null,
        "data_mode": "COMPLETED",
        "top_places": [
          "ब्राबल",
          "Brabal",
          "आमाछोदिङ्मो",
          "Aamachhodingmo",
          "बाहुनडाँडा",
          "Bahun Danda"
        ],
        "top_waterways": [
          "Trishuli River",
          "Bhote Koshi",
          "Langtang Khola",
          "Chilime Khola"
        ],
        "opt_cutoff": null,
        "pess_cutoff": null,
        "unver_routes": null,
        "buildings_destroyed": 0,
        "mtime": 1791172090.2703736
      },
      {
        "run_name": "test_C3_cold",
        "path": "/home/zeus/Downloads/project1/runs/test_C3_cold",
        "label": "आमाछोदिङ्मो / Bhote Koshi (2026-05-15)",
        "event_date": "2026-05-15",
        "bbox": [
          85.3,
          28.1,
          85.42,
          28.25
        ],
        "data_mode": "COMPLETED",
        "top_places": [
          "आमाछोदिङ्मो",
          "Aamachhodingmo",
          "ब्राबल",
          "Brabal",
          "पाजुङ",
          "Pajung"
        ],
        "top_waterways": [
          "Bhote Koshi",
          "Trishuli River",
          "Langtang Khola",
          "Chilime Khola"
        ],
        "opt_cutoff": 2,
        "pess_cutoff": 5,
        "unver_routes": 63,
        "buildings_destroyed": 0,
        "mtime": 1791264649.7030628
      },
      {
        "run_name": "test_C3_cold_final",
        "path": "/home/zeus/Downloads/project1/runs/test_C3_cold_final",
        "label": "आमाछोदिङ्मो / Bhote Koshi (2026-05-15)",
        "event_date": "2026-05-15",
        "bbox": [
          85.3,
          28.1,
          85.42,
          28.25
        ],
        "data_mode": "COMPLETED",
        "top_places": [
          "आमाछोदिङ्मो",
          "Aamachhodingmo",
          "ब्राबल",
          "Brabal",
          "पाजुङ",
          "Pajung"
        ],
        "top_waterways": [
          "Bhote Koshi",
          "Trishuli River",
          "Langtang Khola",
          "Chilime Khola"
        ],
        "opt_cutoff": 0,
        "pess_cutoff": 0,
        "unver_routes": 65,
        "buildings_destroyed": 0,
        "mtime": 1791273214.7044425
      },
      {
        "run_name": "test_C3_cold_run1",
        "path": "/home/zeus/Downloads/project1/runs/test_C3_cold_run1",
        "label": "आमाछोदिङ्मो / Bhote Koshi (2026-05-15)",
        "event_date": "2026-05-15",
        "bbox": [
          85.3,
          28.1,
          85.42,
          28.25
        ],
        "data_mode": "COMPLETED",
        "top_places": [
          "आमाछोदिङ्मो",
          "Aamachhodingmo",
          "ब्राबल",
          "Brabal",
          "पाजुङ",
          "Pajung"
        ],
        "top_waterways": [
          "Bhote Koshi",
          "Trishuli River",
          "Langtang Khola",
          "Chilime Khola"
        ],
        "opt_cutoff": 0,
        "pess_cutoff": 0,
        "unver_routes": 67,
        "buildings_destroyed": 0,
        "mtime": 1791234820.609426
      },
      {
        "run_name": "test_C3_cold_run2",
        "path": "/home/zeus/Downloads/project1/runs/test_C3_cold_run2",
        "label": "आमाछोदिङ्मो / Bhote Koshi (2026-05-15)",
        "event_date": "2026-05-15",
        "bbox": [
          85.3,
          28.1,
          85.42,
          28.25
        ],
        "data_mode": "COMPLETED",
        "top_places": [
          "आमाछोदिङ्मो",
          "Aamachhodingmo",
          "ब्राबल",
          "Brabal",
          "पाजुङ",
          "Pajung"
        ],
        "top_waterways": [
          "Bhote Koshi",
          "Trishuli River",
          "Langtang Khola",
          "Chilime Khola"
        ],
        "opt_cutoff": 0,
        "pess_cutoff": 0,
        "unver_routes": 67,
        "buildings_destroyed": 0,
        "mtime": 1791235006.23676
      },
      {
        "run_name": "test_C3_trishuli_20260515",
        "path": "/home/zeus/Downloads/project1/runs/test_C3_trishuli_20260515",
        "label": "ब्राबल / Trishuli River",
        "event_date": "unknown",
        "bbox": null,
        "data_mode": "COMPLETED",
        "top_places": [
          "ब्राबल",
          "Brabal",
          "आमाछोदिङ्मो",
          "Aamachhodingmo",
          "बाहुनडाँडा",
          "Bahun Danda"
        ],
        "top_waterways": [
          "Trishuli River",
          "Bhote Koshi",
          "Langtang Khola",
          "Chilime Khola"
        ],
        "opt_cutoff": null,
        "pess_cutoff": null,
        "unver_routes": null,
        "buildings_destroyed": 0,
        "mtime": 1791172130.7261484
      },
      {
        "run_name": "test_C4_cold",
        "path": "/home/zeus/Downloads/project1/runs/test_C4_cold",
        "label": "Melamchi / Indrawati river (2021-03-15)",
        "event_date": "2021-03-15",
        "bbox": [
          85.53,
          27.8,
          85.62,
          27.95
        ],
        "data_mode": "COMPLETED",
        "top_places": [
          "Melamchi",
          "Bansbari",
          "Duwachaur",
          "Talamarang",
          "Langarche",
          "Sikharpur"
        ],
        "top_waterways": [
          "Indrawati river",
          "Melamchi River",
          "Indrawati River"
        ],
        "opt_cutoff": 0,
        "pess_cutoff": 0,
        "unver_routes": 0,
        "buildings_destroyed": 0,
        "mtime": 1791264974.6110227
      },
      {
        "run_name": "test_C4_cold_final",
        "path": "/home/zeus/Downloads/project1/runs/test_C4_cold_final",
        "label": "Melamchi / Indrawati river (2021-03-15)",
        "event_date": "2021-03-15",
        "bbox": [
          85.53,
          27.8,
          85.62,
          27.95
        ],
        "data_mode": "COMPLETED",
        "top_places": [
          "Melamchi",
          "Bansbari",
          "Duwachaur",
          "Talamarang",
          "Langarche",
          "Sikharpur"
        ],
        "top_waterways": [
          "Indrawati river",
          "Melamchi River",
          "Indrawati River"
        ],
        "opt_cutoff": 0,
        "pess_cutoff": 0,
        "unver_routes": 0,
        "buildings_destroyed": 0,
        "mtime": 1791273533.3446972
      },
      {
        "run_name": "test_C4_cold_run1",
        "path": "/home/zeus/Downloads/project1/runs/test_C4_cold_run1",
        "label": "Melamchi / Indrawati river (2021-03-15)",
        "event_date": "2021-03-15",
        "bbox": [
          85.53,
          27.8,
          85.62,
          27.95
        ],
        "data_mode": "COMPLETED",
        "top_places": [
          "Melamchi",
          "Bansbari",
          "Duwachaur",
          "Talamarang",
          "Langarche",
          "Sikharpur"
        ],
        "top_waterways": [
          "Indrawati river",
          "Melamchi River",
          "Indrawati River"
        ],
        "opt_cutoff": 0,
        "pess_cutoff": 0,
        "unver_routes": 0,
        "buildings_destroyed": 0,
        "mtime": 1791235831.3271034
      },
      {
        "run_name": "test_C4_cold_run2",
        "path": "/home/zeus/Downloads/project1/runs/test_C4_cold_run2",
        "label": "Melamchi / Indrawati river (2021-03-15)",
        "event_date": "2021-03-15",
        "bbox": [
          85.53,
          27.8,
          85.62,
          27.95
        ],
        "data_mode": "COMPLETED",
        "top_places": [
          "Melamchi",
          "Bansbari",
          "Duwachaur",
          "Talamarang",
          "Langarche",
          "Sikharpur"
        ],
        "top_waterways": [
          "Indrawati river",
          "Melamchi River",
          "Indrawati River"
        ],
        "opt_cutoff": 0,
        "pess_cutoff": 0,
        "unver_routes": 0,
        "buildings_destroyed": 0,
        "mtime": 1791236093.51443
      },
      {
        "run_name": "test_C4_melamchi_20210315",
        "path": "/home/zeus/Downloads/project1/runs/test_C4_melamchi_20210315",
        "label": "Melamchi / Indrawati river",
        "event_date": "unknown",
        "bbox": null,
        "data_mode": "COMPLETED",
        "top_places": [
          "Melamchi",
          "Bansbari",
          "Duwachaur",
          "Talamarang",
          "Langarche",
          "Sikharpur"
        ],
        "top_waterways": [
          "Indrawati river",
          "Indrawati River",
          "Melamchi Khola",
          "Melamchi River"
        ],
        "opt_cutoff": null,
        "pess_cutoff": null,
        "unver_routes": null,
        "buildings_destroyed": 0,
        "mtime": 1791172305.846173
      },
      {
        "run_name": "test_C_no_event",
        "path": "/home/zeus/Downloads/project1/runs/test_C_no_event",
        "label": "ब्राबल / Trishuli River (2026-03-15)",
        "event_date": "2026-03-15",
        "bbox": [
          85.3,
          28.1,
          85.42,
          28.25
        ],
        "data_mode": "COMPLETED",
        "top_places": [
          "ब्राबल",
          "Brabal",
          "आमाछोदिङ्मो",
          "Aamachhodingmo",
          "बाहुनडाँडा",
          "Bahun Danda"
        ],
        "top_waterways": [
          "Trishuli River",
          "Bhote Koshi",
          "Langtang Khola",
          "Chilime Khola"
        ],
        "opt_cutoff": 0,
        "pess_cutoff": 0,
        "unver_routes": 44,
        "buildings_destroyed": 0,
        "mtime": 1791195034.6571634
      }
    ],
    "count": 81
  },
  {
    "tool": "load_run",
    "status": "success",
    "loaded_run": "practice_sikkim_event",
    "label": "Nanga (2023-10-04)",
    "event_date": "2023-10-04",
    "optimistic_cut_off_count": 26,
    "pessimistic_cut_off_count": 27,
    "cloud_unverified_routes": 2,
    "total_settlements": 28,
    "statement": "Loaded run 'practice_sikkim_event' (Nanga (2023-10-04)). In this event, 26 settlements are cut off under optimistic scenario, and 27 settlements are cut off under pessimistic scenario (with 2 connected settlements passing through cloud-unverified segments).",
    "fact_ids": [
      "event.date",
      "cutoff.vehicle.optimistic.count",
      "cutoff.vehicle.pessimistic.count",
      "cutoff.vehicle.optimistic.connected_unverified"
    ]
  }
]
```

#### Model Answer:
In Sikkim, during the event on October 4, 2023, there were 26 settlements cut off under the optimistic scenario and 27 settlements cut off under the pessimistic scenario. Additionally, there were 2 connected settlements that passed through cloud-unverified segments.

---
