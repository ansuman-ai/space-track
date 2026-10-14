# Spaceborne Rapid Flood & Debris Damage Assessment

> **Educational prototype, not an operational tool.**

A dynamic, reproducible geospatial pipeline to detect flood extent, identify debris flows, grade infrastructure damage from pre-event OpenStreetMap vectors, and isolate cut-off mountain settlements from raw satellite and elevation data.

---

## Quick Start for Judges & Evaluators

### 1. One-Click Setup
```bash
./setup.sh
```
*(Installs requirements, compiles the C-accelerated HAND library, and verifies environment).*

### 2. Launch the Interactive Dashboard & Bilingual Copilot
```bash
python3 -m uvicorn src.dashboard.app:app --host 127.0.0.1 --port 8000
```
Open **[http://127.0.0.1:8000](http://127.0.0.1:8000)** in your browser:
- Start screen displays the interactive Himalayan extent map and place search.
- Explore any of the **7 verified disaster assessments** from the menu or start screen.
- Interact with the bilingual SitRep Copilot (English, Nepali, Hindi) with strict number-guard verification and anti-hallucination protection.

### 3. Verify All Shipped Runs (Bit-for-Bit Consistency)
```bash
python3 scripts/check_dashboard_data.py
```
*(Validates all 72 runs and proves that API, Copilot FactStore, SitRep, and raw JSON deliverables match bit-for-bit).*

### 4. Run an End-to-End CLI Assessment (Cold Run)
```bash
python3 main.py --bbox 85.30 28.10 85.42 28.25 --event-date 2026-08-26 --out-dir runs/my_trishuli_run --no-cache
```

### 5. Run Security & Copilot Evaluation Suites
```bash
# Security & path-traversal audit (9/9 passed)
PYTHONPATH=. pytest tests/test_security_audit.py -v

# Copilot targeted evaluation suite (22 targeted questions live)
python3 scripts/run_eval_v112.py
```


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

## Terrain-Adaptive Inundation Path & Flat-Floodplain Validation Caveat

The pipeline adaptively partitions terrain into `steep_valley` vs `flat_floodplain` regimes via DEM slope and Height Above Nearest Drainage (HAND) distributions:
- **Steep-Valley Regime**: Retains the frozen mountain debris-flow/flood path without modification (guaranteeing bit-for-bit identity for Himalayan benchmark events A and B). Outputs carry `"validation_status": "validated on EMSR927 (F1 0.57, precision 0.94)"`.
- **Flat-Floodplain Regime**: Bypasses stream-proximity pruning and incorporates multi-sensor Sentinel-1 SAR change log-ratio (VV/VH) and Sentinel-2 optical water indices ($\Delta\text{MNDWI}$, $\Delta\text{NDWI}$, turbid water NIR absorption) with seasonal paddy and permanent baseline water subtraction.
- **Detector Selection**: Selected between candidates based on official Copernicus EMS validation:
  - Greece Storm Daniel (EMSR692 AOI02, Thessaly Plain): Combined S1+S2 achieved **F1 0.59** (IoU 0.42, precision 0.60, recall 0.58) with **0.0000 km²** false alarms on the no-event test.
  - Italy Emilia-Romagna (EMSR659 AOI01, Conselice / Ravenna): S1-threshold captured 10.65 km² (F1 0.35; surface floodwaters largely receded before the first clear post-event Sentinel-2 optical scene on May 23).
  - Kuro Siwo deep learning SNUNet was rejected for flat default due to a 235 km² false alarm on Mediterranean dry terrain (see `docs/kurosiwo_results.md`).
- **Scientific Integrity Caveat**: *The flat-floodplain detector choice (Combined S1+S2) was selected using EMS validation on Greece and Italy. Although thresholds were derived from control distributions and verified on no-event tests rather than manually tuned to EMS boundaries, this detector selection must be confirmed on additional flat-floodplain flood events as more official vector packages become available.* Outputs carry `"validation_status": "validated on 1 event (EMSR692 Greece, F1 0.59); weak on EMSR659 Italy (F1 0.35, flood receded before clear optical)"`.

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

The selected default configuration (`min_d_bsi_floor: 0.18`, `inferred_min_reach_fraction: 0.20`, `inferred_min_observed_pixels: 50`) uniquely passed all no-event tests (all $< 0.024\text{ km²}$, 0 buildings, 0 cut-offs) while preserving flood and debris detection across Events A and B.

### Channel Threshold Cap Verification (No-Event Tests)
To prevent control noise overestimation in river channels while strictly guarding against false alarms, a channel threshold cap was evaluated across candidate caps `{0.55, 0.60, 0.65, none}` where `channel threshold = min(control/seasonal-derived value, cap)`.
- All threshold caps were evaluated across the cross-season no-event tests C1–C4.
- All candidate caps satisfied the no-event rejection rule ($< 0.07\text{ km²}$ affected area, 0 buildings, 0 bridges, 0 cut-offs across C1–C4).
- Following the non-EMS selection rule, the lowest (most sensitive) passing cap was selected: `channel_cap: 0.55`.

## Dashboard & Visualizer (Layer 7)

Launch the interactive emergency dashboard with a single command:
```bash
python3 -m src.dashboard.app
```
or via uvicorn directly:
```bash
uvicorn src.dashboard.app:app --host 127.0.0.1 --port 8000
```
Open [http://127.0.0.1:8000](http://127.0.0.1:8000) (or [http://localhost:8000](http://localhost:8000)) in your browser.

Features:
- Dynamic discovery of historical runs (`runs/` directory)
- Map-first interface with toggleable vector and raster hazard/infrastructure layers
- Pre-event OSM damage grading & flood classification
- Severed transportation network routing & cut-off settlement analysis
- Bilingual English / Nepali UI toggle
- Zero hardcoded place names or statistics; all data parsed dynamically from pipeline JSONs.

---

## Remote Ingestion Performance & GDAL Range Request Optimization

### Micro-Benchmark & Root Cause Investigation
Planetary Computer and Azure Blob Storage mis-handle merged or multiplexed HTTP/2 range requests on remote Cloud-Optimized GeoTIFFs (COGs), issuing `206 Partial Content` responses that GDAL’s internal curl driver flagged as transport errors (`CPLE_AppDefined: Request for X-Y failed with response_code=206`). This led to repeated timeouts, exponential retries, and severe runtime regressions during Sentinel-2 band fetching.

A micro-benchmark was performed reading the Sentinel-2 B04 sub-window over the Trishuli bounding box across 4 GDAL configurations (with an empty VSI cache per repetition):

| Configuration | Parameters | Repetition 1 | Repetition 2 | 206 Warnings |
|---|---|---|---|---|
| **1) Previous Settings** | `HTTP/2, MULTIPLEX=YES, MERGE=YES` | 67.24 s (4.03 MB) | 19.56 s (4.03 MB) | 2 (Intermittent hangs) |
| **2) HTTP/1.1 Single-stream** | `HTTP/1.1, MULTIPLEX=NO, MERGE=YES` | 14.67 s (4.03 MB) | 16.70 s (4.03 MB) | **0** |
| **3) No Merged Ranges** | `HTTP/2, MULTIPLEX=YES, MERGE=NO` | 16.28 s (4.03 MB) | 18.61 s (4.03 MB) | **0** |
| **4) Combined (Selected)** | `HTTP/1.1, MULTIPLEX=NO, MERGE=NO` | **15.11 s** (4.03 MB) | **18.07 s** (4.03 MB) | **0** |

Configuration 4 (`GDAL_HTTP_VERSION="1.1"`, `GDAL_HTTP_MULTIPLEX="NO"`, `GDAL_HTTP_MERGE_CONSECUTIVE_RANGES="NO"`) was committed to `src/l0_ingestion/gdal_env.py` with `GDAL_HTTP_MAX_RETRY="2"`, completely eliminating all 206 retry penalties and connection stalls.

### Measured Cold Run Timings (`--no-cache`)
A fresh cold Trishuli pipeline execution with `--no-cache` and empty caches was verified:
- **Total Pipeline Duration**: **574.8 s** (~9.6 min, down from >1200 s).
- **L0 Ingestion Sub-step Times**:
  - `s2` (Sentinel-2 multi-scene fetch & composite): 482.5 s (164.4 MB downloaded)
  - `s1` (Sentinel-1 RTC pre & post SAR): 113.5 s (61.5 MB downloaded)
  - `dem` (Copernicus DEM-30 tile read & clip): 57.3 s (5.3 MB downloaded)
  - `osm_buffered` (Overpass road/bridge corridor network): 56.1 s (15.6 MB downloaded)
  - `osm_bbox` (Overpass primary footprint ingestion): 49.8 s (3.6 MB downloaded)
- **Subsequent Layers**:
  - `L1 Preprocessing`: 13.8 s
  - `L2 Detection`: 20.0 s
  - `L4 Damage Grading`: 5.5 s
  - `L5 Network Routing & Isolations`: 66.8 s
- **Bit-for-Bit Identity**: All 11 output files (`hazard_classes.tif`, `buildings_graded.geojson`, `bridges_graded.geojson`, `damage_summary.json`, `settlements.geojson`, etc.) remain **11/11 bit-for-bit MD5 identical** to benchmark Test A.

---

## Copilot Assistant

The disaster assessment Copilot provides interactive natural-language querying of damage statistics, road blockages, bridge outages, cut-off settlements, and prioritized repair corridors.

### Operating Modes

1. **Offline Mode (Default / Zero-Config)**:
   - Works immediately out of the box **without any API key or external internet access**.
   - Backed by a deterministic, grounded rule-and-template synthesis engine running against pipeline output files (`damage_summary.json`, `cutoff_summary.json`, `repair_packages.json`, etc.).
   - Responses generated in offline mode are explicitly labelled with `[ANSWERED IN OFFLINE MODE]` in the chat interface.

2. **Live LLM Mode**:
   - Provides tool-calling conversational interaction in English, Nepali (नेपाली), and Hindi (हिन्दी).
   - Enforces a strict two-pass `NumberGuard` that verifies every quantitative claim against tool output payloads, instantly rejecting hallucinations.
   - Requires the user to provide their own API key(s) in a local `.env` file at the repository root.

### Supported Providers & Environment Variables

Place your keys in `.env` (comma-separated if using multiple keys for automatic rotation):

| Provider | Environment Variable | Key Format | Default Models |
| :--- | :--- | :--- | :--- |
| **Groq** | `GROQ_API_KEYS` (or `GROQ_API_KEY`) | `gsk_...` | `openai/gpt-oss-120b`, `openai/gpt-oss-20b` |
| **Google Gemini** | `GEMINI_API_KEYS` (or `GEMINI_API_KEY`) | `AQ....` / `AIza...` | `gemini-3.1-flash-lite`, `gemini-3.5-flash-lite` |
| **OpenRouter** | `OPENROUTER_API_KEYS` (or `OPENROUTER_API_KEY`, `PLATFORM_API_KEY`) | `sk-or-...` | `openai/gpt-4o-mini` |

> [!CAUTION]
> **Never commit your `.env` file.** `.env` is ignored by `.gitignore`. Do not commit, log, or push API keys to any git repository.

### Key Rotation & Fast Failover
- **Intra-Provider Rotation**: If an active API key encounters a 429 rate limit or quota exhaustion, Copilot automatically rotates to the next active key for the same provider immediately before failing over to the next provider.
- **Provider Failover Order**: `Groq` $\to$ `Gemini` $\to$ `OpenRouter` $\to$ `Offline Mode`.
- **Latency Protection**: Individual provider calls timeout after 6.0 s; whole-turn latency is strictly capped at 8.0 s before falling back cleanly to offline synthesis.

---

## Installation & Build

### 1. Requirements
Install Python dependencies:
```bash
pip install -r requirements.txt
```

### 2. C Extension Compilation (HAND Acceleration)
To accelerate D8 flow accumulation and downstream drainage elevation propagation in Layer 1, compile the shared C library:
```bash
gcc -O3 -shared -fPIC src/l1_preprocessing/hand_c.c -o src/l1_preprocessing/libhand_fast.so
```

### 3. Portability & Automatic Python Fallback
- If `gcc` is not available or `libhand_fast.so` cannot be loaded, the pipeline automatically detects the missing module, logs a warning, and falls back seamlessly to the vectorized pure-Python implementation.
- To explicitly force the pure-Python implementation (e.g. for testing or non-C environments), set `HAND_DISABLE_C=1` in your environment.
- **Byte-Identity Guarantee**: The C extension and the Python fallback produce bit-for-bit identical results (`Max diff HAND: 0.0`, byte-identical `hand.tif`).

### 4. Optional Pretrained Weights (Kuro Siwo SNUNet Detector)
The default operational path uses the physics-informed Sentinel-2 + Sentinel-1 engine (`detector: "combined"`) and requires zero deep learning model weights.

If executing with the optional experimental detector (`detector: "kurosiwo"`):
1. Create the `weights/` directory:
   ```bash
   mkdir -p weights
   ```
2. Place the pretrained Kuro Siwo SNUNet checkpoint `best_segmentation.pt` in `weights/`:
   ```bash
   # Checkpoint file path: weights/best_segmentation.pt
   ```
3. Verify the checksum:
   ```bash
   md5sum weights/best_segmentation.pt
   # Must match: 07c6f40cb71290d93ba232ab03f74b1e
   ```
If `weights/best_segmentation.pt` is absent or checksum verification fails when `detector: "kurosiwo"` is explicitly configured, the pipeline terminates with an actionable error.

---

## Data Sources & Attributions

- **Sentinel Imagery (S1 SAR & S2 MSI)**: Ingested dynamically from Microsoft Planetary Computer STAC API (`planetarycomputer.microsoft.com`). *"Contains modified Copernicus Sentinel data 2026."*
- **Digital Elevation Model**: Copernicus WorldDEM-30 ingested via AWS Open Data Registry (`copernicus-dem-30m.s3.amazonaws.com`). *"Produced using Copernicus WorldDEM-30 © DLR e.V. 2010–2014 and © Airbus Defence and Space GmbH 2014–2018 provided under COPERNICUS by the European Union and ESA; all rights reserved."*
- **Vector Baseline Infrastructure**: Historical pre-event snapshot query via ohsome API / HeiGIT (`api.ohsome.org`) pinned to the event date to prevent post-event OSM editing artifacts.
- **Orientation Basemap**: Current OpenStreetMap standard raster tiles used strictly for cartographic orientation under the Open Database License (ODbL). *"© OpenStreetMap contributors."*
- **Copernicus EMS Validation**: Official vector delineation/grading packages for EMSR927, EMSR692, and EMSR659. *"European Union, Copernicus Emergency Management Service data (EMSR927, EMSR692, EMSR659)."*
- **Citation**: Bountos et al., 2024 (*Kuro Siwo*).
- **Disclaimer**: *Educational prototype, not an operational tool.*

> [!NOTE]
> The flat-terrain detector was tuned on European events (EMSR692 Greece, EMSR659 Italy) and should be confirmed on local flood data when applying to new regions.

---

## Known Issues and Security Considerations

1. **Planetary Computer Range Response Retries**:
   - Upstream Planetary Computer blob storage servers may return HTTP 206 responses that can cause GDAL HTTP range merge retry loops if HTTP/2 range multiplexing is enabled.
   - **Resolution/Mitigation**: The system configures GDAL environment settings (`GDAL_HTTP_VERSION=1.1`, `GDAL_HTTP_MERGE_CONSECUTIVE_RANGES=NO`) to ensure sequential, deterministic range reading without retries.
2. **WeasyPrint Untrusted Resource Loading (CVE-2026-106443 / PYSEC-2026-3940)**:
   - Untrusted image dispatch in older WeasyPrint builds can attempt external fetches or format dispatch.
   - **Resolution/Mitigation**: The situation report PDF engine binds `safe_url_fetcher` which strictly forbids external and local URL requests (`ValueError`), while all Markdown inputs are sanitized with `html.escape`.
3. **Local Road Corridor Segmentation**:
   - In complex mountainous valley networks, intersecting arterial and feeder road segments share naming conventions. Local spatial queries clip geometries strictly to Euclidean circles and prioritize arterial classes (`primary`) over local access paths.
4. **Offline Environment Deployment**:
   - The dashboard and Copilot operate in complete isolation without external API dependencies. All UI fonts (IBM Plex Sans, IBM Plex Mono, IBM Plex Sans Devanagari) and map assets are bundled locally. In the absence of live LLM API keys or network access, Copilot automatically falls back to deterministic rule-grounded offline synthesis with explicit UI disclosure.

---

## Troubleshooting

- **Remote Ingestion / DNS Timeouts (HTTP Error 0 / Hanging Reads)**:
  - If downloads hang or show HTTP error 0, check DNS speed (`curl -o /dev/null -s -w "%{time_namelookup}\n" https://planetarycomputer.microsoft.com`) and switch DNS to `1.1.1.1` / `8.8.8.8`. Slow system DNS resolution (>2s) causes curl/GDAL socket timeouts on cloud STAC endpoints before connections are established.

