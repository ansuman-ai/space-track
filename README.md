# Spaceborne Rapid Flood & Debris Damage Assessment

A dynamic, reproducible geospatial pipeline to detect flood extent, identify debris flows, grade infrastructure damage from pre-event OpenStreetMap vectors, and isolate cut-off mountain settlements from raw satellite and elevation data.

---

## Architecture & Layers Overview

- **L0 Ingestion**: Dynamic ingestion of Sentinel-1 RTC pairs, Copernicus DEM-30, and historical OSM snapshots via ohsome API.
- **L1 Preprocessing**: Radiometric calibration, RTC terrain flattening, same-orbit track alignment, and cloud masking.
- **L2 Flood & Debris Mapping**: Dual-mechanism change detection (water drop on low slope, debris surge on mountain slopes, radar shadow/layover masking).
- **L6 AI Flood Segmentation Model** *(Parallel with L2)*: Deep learning water segmentation trained on Kuro Siwo multi-temporal SAR + DEM slope.
- **L3 EMSR927 Validation**: Benchmark comparison strictly isolated in `validation/`.
- **L4 OSM Damage Grading**: Spatial damage classification (Destroyed, Damaged, Possibly damaged) against pre-event OSM inventory.
- **L5 Cut-off Settlement Analysis**: Network routing on severed road graphs to identify isolated communities (fallback to nearest town if no hospital exists).
- **L7 Dashboard & Bilingual SitRep**: Interactive web map and automated 1-page situational report in English and Nepali.
- **L8 Hydrological Flow Tracing**: Upstream-to-downstream D8 elevation drainage tracing.

---

## Known Limitations & Model Scope

1. **Debris Class Limitation in AI Model**:
   - The Kuro Siwo training dataset features annotated flood inundation and permanent water classes, but **contains no debris flow class**.
   - Consequently, the AI segmentation model (L6) exclusively segments flood water.
   - Debris flows are mapped via a dedicated, physically grounded rule-based detector (L2) combining SAR co-polarized backscatter increase ($\Delta\gamma^0 > +2\text{ to }+3\text{ dB}$), spatial texture variance, slope, and drainage corridor proximity.
2. **Satellite Revisit Times**:
   - Sentinel satellites have revisit intervals of 6 to 12 days per orbital track, meaning satellite SAR cannot detect flash floods minutes before impact or replace real-time telemetry.
3. **Radar Geometry in Mountain Terrain**:
   - Steep slopes cause radar layover and shadow. Areas subject to geometric distortion are masked using DEM-derived look-angle calculations.
4. **OpenStreetMap Data Sparsity**:
   - In rural and mountainous areas, building and road footprints in OSM may be sparse or incomplete. Low damage counts from incomplete pre-event OSM mapping represent an inventory limitation, not a pipeline failure.

---

## Required Data Attribution

- *"Contains modified Copernicus Sentinel data 2026."*
- *"Produced using Copernicus WorldDEM-30 © DLR e.V. 2010–2014 and © Airbus Defence and Space GmbH 2014–2018 provided under COPERNICUS by the European Union and ESA; all rights reserved."*
- *"© OpenStreetMap contributors."*
- *Training dataset citation: Bountos et al., "Kuro Siwo: 33 billion m² under the water. A global multi-temporal satellite dataset for rapid flood mapping", NeurIPS 2024.*
- *Validation data credit: "European Union, Copernicus Emergency Management Service data (EMSR927)".*
