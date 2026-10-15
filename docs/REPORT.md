# Space Track: Mapping Flood Damage from Space

**Oct 14, 2026 · @Ansuman**

---

## 1. Summary

Space Track turns an area and a flood date into answers to three rescue questions (where the flood hit, what was damaged, who is cut off) using only Sentinel-1, Sentinel-2, Copernicus DEM and pre-event OpenStreetMap. It outputs a map dashboard, a one-page English/Nepali situation report and a copilot whose every number comes from the system's own outputs.

### Trishuli flood, 26 Aug 2026

| Metric | Result |
| :--- | :--- |
| Affected area | 1.08 km² observed + 1.07 km² inferred from terrain |
| Agreement with EMSR927 | precision 0.94, recall 0.41, F1 0.57 |
| Damage | 107 buildings destroyed (225 affected), 12 bridges destroyed |
| Cut off from any town or hospital | 44 settlements by road, 4 with no ground access |
| Repair first | 4 links reconnect 19 settlements (939 buildings) |
| No-event dates (6) | 0 damage, 0 settlements cut off |
| Cold run on a laptop | 248 s, 4.1 GB RAM |

---

## 2. Data and rules

Only the allowed inputs are used; the EMS maps (EMSR927, EMSR692, EMSR659) sit in a validation folder that the pipeline never reads.

| Input | Source | Use |
| :--- | :--- | :--- |
| Sentinel-2 L2A | Planetary Computer | optical change; primary for debris |
| Sentinel-1 RTC | Planetary Computer | radar change through cloud; same orbit, 12 days apart |
| Copernicus DEM GLO-30 | AWS Open Data | slope, height above drainage (HAND), flow paths |
| OpenStreetMap | ohsome, snapshot before the event (27 Jul 2026) | buildings, roads, bridges, health facilities, towns |

Each run uses an event pair, a control pair 12 days earlier (normal change) and a seasonal control one year earlier (seasonal water). The dashboard basemap and place search use current OSM for orientation only.

---

## 3. Where did the flood hit, what was damaged

The system classifies the terrain first and runs the matching detector; thresholds come from the area's own control images, with floors fixed on no-event dates only.

1. **Ingest and pre-process.** Parallel downloads; Lee speckle filter; slope, HAND (C implementation) and radar shadow mask from the DEM.
2. **Terrain regime.** Flat floodplain if median slope < 8°, over 40% of pixels below 5° and over 50% within 15 m of drainage (Assam 0.8°); otherwise steep valley (Trishuli 33°).
3. **Steep valley.** Debris shows mainly in optical images: vegetation loss (ΔNDVI), new bare soil (ΔBSI), channel change vector and built-up change; radar is used under cloud. Observed damage is class 2; class 3 extends it along the same river reach using HAND, only where enough of the reach was observed.
4. **Flat floodplain.** Water now (radar, or optical water index when clear), not water before, and not water in the same season a year earlier; this removed most paddy water in Assam. Without the seasonal image the run is marked DEGRADED.
5. **Damage grading.** A building is destroyed if over 50% of its footprint is in class 2, damaged within 10 m, possibly damaged in class 3 or within 30 m; bridges use a 30 m buffer and a 100 m reach rule; roads are graded per segment. Anything under cloud is "not verified". Flat runs use flooded grades.

Two cold runs give byte-identical outputs.

---

## 4. Who is cut off, and what to repair first

A settlement is cut off if it reached a town or health facility by road before the event but not after; settlements without road access before the event are excluded.
- Settlements are OSM places plus building clusters, named "Near <place> (<km>)".
- Destinations are health facilities and towns in a 30 km buffer.
- Vehicle and walking networks; cut off on both = no ground access (air or boat). Roads under cloud count as open (optimistic) or closed (pessimistic).
- Repair packages: the destroyed links on each settlement's best pre-event route, grouped and ranked by settlements and buildings reconnected.
- Trishuli: 44 settlements cut off in both scenarios, 4 with no ground access (near Dalphedi and Lingling, 60 buildings), 23 more reachable only through cloud. Best single repair: 265 m of the Pasang Lhamu Highway (NH42), 2 settlements; package 1 (4 links, about 1 km) reconnects 19 settlements and 939 buildings.

---

## 5. Results

Where it detects damage the system agrees closely with EMSR927, and it reported no damage on any no-event date.

Trishuli vs EMSR927 (first clear optical image 27 Aug, one day after; radar 16 and 28 Aug): area precision 0.94, recall 0.41, F1 0.57, IoU 0.40; road cuts precision 1.00, recall 0.37; 3 of 5 EMS-destroyed bridges found. Misses are mostly narrow side-stream damage and areas under cloud or shadow.

| Run | Terrain | Observed / inferred km² | Buildings destroyed (affected) | Bridges destroyed | Cut off / no ground access |
| :--- | :--- | :---: | :---: | :---: | :---: |
| Trishuli 2026-08-26 | mountain | 1.08 / 1.07 | 107 (225) | 12 | 44 / 4 |
| Melamchi 2021-06-15 | mountain | 0.90 / 0.99 | 72 (280) | 4 | 5 / 5 |
| Sikkim 2023-10-04 | mountain | 0.42 / 0.98 | 47 (161) | 5 | 8 / 8 |
| Chamoli 2021-02-07 | mountain | 0.27 / 0.17 | 0 (1) | 1 | 0 / 0 |
| Assam 2024-07-02 | flat | 17.36 / – | 9 flooded (13) | 0 | 5 / 5 |

Only Trishuli has an official reference here; the others test that the system transfers unchanged. Chamoli is a failure case (winter snow, sparse 2021 OSM; Section 8). On flat terrain against EMS maps: Thessaly EMSR692 F1 0.59 (precision 0.60, recall 0.58), Emilia-Romagna EMSR659 F1 0.35 (water receded before the first clear image); these scores also guided the detector choice. On six no-event dates the system found 0.00-0.05 km² of noise and 0 damaged buildings, bridges or cut-offs. A fresh clone reproduced all 11 Trishuli outputs byte for byte.

---

## 6. AI component

Our AI component is the situation-report copilot; we also trained a Kuro Siwo model and explain why it is not the default.

**Copilot.** It answers questions in English, Nepali or Hindi about the open run and links the one-page report.
- **Tools only:** the language model reads the run files through tools, and every answer names the run it used.
- **Guards:** each number must match the field it came from in this turn's tool outputs; place names, road refs and ids must appear there too; no causes, deaths, population or estimates from user assumptions.
- **Safe output:** the report is filled from run files by a template, never written by the model; without an API key it answers in a labelled offline mode; providers fail over within an 8 s budget.

| Test set | Questions | Result |
| :--- | :---: | :--- |
| Held-out rescue questions (EN/NE/HI) | 15 | 100% verified factual grounding |
| Hallucination traps | 20 | 0 invented numbers or names |
| Small talk, typos, report requests | 12 | Handled safely, offline templates served |

Testing caught and the guards now block: answering from the wrong event, calling an unmatched road "open", and sending helicopters to all 44 road cut-offs instead of the 4 without ground access.

**Kuro Siwo model.** The pretrained SNUNet reached F1 0.86 (precision 0.83) on Kuro Siwo test events; fine-tuning with the official settings raised validation F1 from 0.66 to 0.72 but not test F1 (0.85), so we kept the published weights. It does not transfer to our scenes: in the Trishuli gorge the radar change is only about 0.06 dB (radar-only best F1 0.18 vs 0.57 for our detector), and on Thessaly it found 14% of the flood while marking 235 km² on a dry date. It stays an optional, experimental detector.

---

## 7. Dashboard and how to run

On the start screen a user searches a place, adjusts the box (up to 0.5° per side), picks the date and presses "Analyse this area"; progress and any failure reason are shown. The run view shows hazard, graded infrastructure, cut-off settlements and repair packages, a Sentinel-2 before/after slider, flow-path tracing from any clicked point (bonus task), tabs Impact / Access / Repair / Confidence, the situation report (EN/NE) and a floating copilot.

To run: install the pinned requirements, build the C library, then:
```bash
# Dashboard
python3 -m src.dashboard.app

# Or CLI
python3 main.py --bbox W S E N --event-date YYYY-MM-DD
```

---

## 8. Limitations

This is an educational prototype, not an operational tool: it maps damage after the fact, misses part of it, and depends on free data.
- **No warning.** The first usable image arrives 1-12 days after an event (revisit time, cloud).
- **Recall.** 0.41 of the EMS area and 0.37 of its road cuts on Trishuli; narrow damage is below 10-20 m resolution.
- **Cloud, snow, shadow.** Radar barely sees debris in steep gorges; snow hid Chamoli; anything under cloud is "not verified" (1,196 buildings and 32 km of road in Trishuli).
- **Modelled areas.** Class 3 comes from terrain (HAND), not from imagery.
- **OpenStreetMap.** Unmapped buildings, roads and bridges cannot be assessed; there is no population data, so we never estimate people affected.
- **Flat terrain.** Checked on only two EMS events whose scores also guided the design; flooded vegetation and floods that recede before a clear image are missed.
- **Inputs.** Results depend on a correct event date and a stable connection to Planetary Computer and AWS.

Known issues are listed in the README.

---

## 9. Attribution and citations

- Contains modified Copernicus Sentinel data 2026.
- Produced using Copernicus WorldDEM-30 © DLR e.V. 2010–2014 and © Airbus Defence and Space GmbH 2014–2018 provided under COPERNICUS by the European Union and ESA; all rights reserved.
- © OpenStreetMap contributors.
- European Union, Copernicus Emergency Management Service data (EMSR927, EMSR692, EMSR659), used for checking only.
- Bountos et al., 2024, Kuro Siwo: 33 billion m² under the water, NeurIPS 2024.
- OpenStreetMap-derived outputs are published under the ODbL. Educational prototype, not an operational tool.
