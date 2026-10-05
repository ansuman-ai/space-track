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

## Layer 2.1 In-Channel Change Detection Update & Scientific Caveat

Following inspection of Copernicus EMS EMSR927 validation results (AOI01 Syabru Besi), an in-channel change detector was added to Layer 2 to capture debris-filled central river channels:
- **Detector**: Change vector magnitude over Sentinel-2 bands (B2, B3, B4, B8, B11, B12 post vs. pre) plus $\Delta\text{NDWI}$ and $\Delta\text{BSI}$, applied inside the pre-event river bed and HAND corridor.
- **Thresholding**: Thresholds are computed adaptively from the clear CONTROL Sentinel-2 pair (99th percentile) with zero ground-truth leakage or manual tuning on EMS.
- **Scientific Integrity Caveat**: *This detector update was made after seeing validation data on the Trishuli/Syabru Besi event. While thresholds were strictly derived from the control scene rather than tuned to EMS, this methodological addition must be independently confirmed and evaluated on other flood/GLOF events.*

---

## Layer 2.4 Final Detector: Variant C Selection & Validation Caveat

Following a 5-way ablation study (Variants A–E), Variant C was selected as the final Layer 2 pipeline configuration:
- **Components**: Original D8 HAND (unmodified, non-pit-filled) + Built-up Change Vector Magnitude (CVM over B2, B3, B4, B8, B11, B12 on OSM building footprints) + Intact-Vegetation Filter (`post_ndvi >= 0.40` and `|d_ndvi| <= 0.20` in hydraulic fill).
- **Ablation Findings**: Native DEM pit-filling (Variant D/E) artificially split reaches and suppressed confluence flood stages while admitting false forest patches; Variant C eliminates false valley-wall fills while preserving the complete confluence flood stage (Strict IoU: 0.570, F1: 0.726, Precision: 0.958; 20m IoU: 0.712, F1: 0.863, Precision: 0.989).
- **Scientific Integrity Caveat**: *Variant C was selected by an ablation that used EMSR927 metrics, so it must be confirmed on other events.*
- **Independent Verification Artifacts**: Verification script `validation/verify_metrics.py` and visual comparison `validation/verify_A_vs_C.png` are maintained in the repository.

---

## False-Alarm Guards & Selection Methodology (No-Event Tests Only)

To eliminate false-alarm settlement isolations and spurious detections during non-disaster periods, principled physical and topological guards were incorporated into Layer 2:
1. **Physical Change Floors**:
   - `min_abs_d_ndvi_floor: -0.20`: Debris flows strip vegetation completely, whereas seasonal phenology maintains $|\Delta\text{NDVI}| < 0.15$.
   - `min_d_bsi_floor: 0.18`: Fresh mineral sediment deposition raises BSI by $\ge +0.18$.
   - `min_channel_cvm_floor: 0.20`: Scour vector magnitude across multi-spectral bands exceeds $0.20$ inside riverbeds.
   - `min_builtup_cvm_floor: 0.15`: Structural building collapse and rubble change multi-spectral reflectance by $\ge 0.15$.
2. **Seasonal Control Pair**:
   - Uses a control pair from the identical calendar dates 1 year earlier (`seasonal_control_lookback_days: 365`) to capture annual seasonal phenology. The stricter of normal and seasonal control thresholds is applied.
3. **Inferred Reach Guard**:
   - `inferred_min_reach_fraction: 0.20` & `inferred_min_observed_pixels: 50`: A stream reach is only hydraulically filled if observed damage touches at least 20% of the channel reach length and has $\ge 50$ pixels, preventing isolated hillside false alarms from triggering broad valley fills.

### Selection Without EMSR927
To guarantee zero benchmark leakage and ensure real-world generalization, guard parameters were evaluated over a 24-combination grid across **four cross-season no-event test datasets**:
- **Test C1**: Trishuli Dry Season (`2026-03-15`)
- **Test C2**: Trishuli Post-Monsoon (`2025-11-15`)
- **Test C3**: Trishuli Pre-Monsoon (`2026-05-15`)
- **Test C4**: Melamchi Dry Season (`2021-03-15`)

**Selection Rule**:
1. Strictly reject any parameter set where any no-event test has total affected area $\ge 0.07\text{ km²}$, $> 0$ affected buildings, or $> 0$ cut-off settlements.
2. Among passing configurations, select the least restrictive one (maximizing detected affected area on disaster events A + B).
3. EMSR927 validation metrics were evaluated strictly *after* parameter selection to ensure zero leakage.

The selected default configuration (`min_d_bsi_floor: 0.18`, `inferred_min_reach_fraction: 0.20`, `inferred_min_observed_pixels: 50`) uniquely passed all no-event tests (all $< 0.024\text{ km²}$, 0 buildings, 0 cut-offs) while preserving $4.856\text{ km²}$ of true flood and debris detection across Events A and B.

---

## Required Data Attribution

- *"Contains modified Copernicus Sentinel data 2026."*
- *"Produced using Copernicus WorldDEM-30 © DLR e.V. 2010–2014 and © Airbus Defence and Space GmbH 2014–2018 provided under COPERNICUS by the European Union and ESA; all rights reserved."*
- *"© OpenStreetMap contributors."*
- *Training dataset citation: Bountos et al., "Kuro Siwo: 33 billion m² under the water. A global multi-temporal satellite dataset for rapid flood mapping", NeurIPS 2024.*
- *Validation data credit: "European Union, Copernicus Emergency Management Service data (EMSR927)".*
