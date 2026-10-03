# Project Rules & Operating Constraints

1. **No Synthetic, Cached, or Fallback Data**: Every pipeline run must fetch real data dynamically. If a fetch fails, fail hard and immediately exit `FAILED` with a clear error trace. Never mock or use placeholder data.
2. **Strictly Allowed Inputs Only**:
   - Sentinel-1 GRD & Sentinel-2 L2A (via Planetary Computer / Copernicus Data Space APIs).
   - Copernicus DEM GLO-30 (elevation and terrain correction).
   - OpenStreetMap pre-event snapshot via ohsome API (`time` parameter strictly before event date derived dynamically from input arguments). Never use Overpass.
   - Kuro Siwo (and optional Sen1Floods11) solely for AI flood model training.
   - Official Copernicus EMS EMSR927 data must ONLY exist and be used inside `validation/` for benchmarking. Never feed into pipeline.
3. **Zero Hardcoded Parameters**: No hardcoded place names, bounding boxes, event dates, orbit paths, or filesystem paths. All parameters must be passed cleanly via CLI args, function arguments, or external configs (e.g. test configs).
4. **Strict Modular Layer Isolation**: Work on ONE layer at a time (L0 to L8). Do not touch, modify, or break other layers when developing or refactoring a layer.
5. **Data Grounding & Truth in Reporting**: Every figure, metric, and percentage shown in tables, dashboards, and reports must be directly calculated by code from the processed data. If uncalculated, print `"not computed"`. No fake or hallucinated confidence scores.
6. **Task Completion Deliverables**: After each task/layer is completed, output:
   - Output file path(s).
   - Key computed numbers/metrics.
   - Exactly one verification plot or visualization.
   - Max 10 lines of concise explanatory text.

---

### Layer-Specific Rules & Specifications (Updated Plan)

- **L0 (Ingestion)**: Credentials and signing via environment variables (`PC_SDK_SUBSCRIPTION_KEY`, `CDSE_CLIENT_ID`, `CDSE_CLIENT_SECRET`). If any fetch fails: exit `FAILED` with the exact error.
- **L1 (Preprocessing)**: Radiometric calibration, RTC terrain flattening, same-orbit track alignment, cloud masking.
- **L2 (Flood & Debris Mapping)**:
  - Do NOT exclude slopes > 25° across the board (debris flow sits on steep mountain slopes).
  - Mask radar shadow/layover derived from DEM + satellite look angle geometry.
  - Apply slope limit ($< 5^\circ$ or low HAND) exclusively to standing flood water, never debris.
  - Debris flow detected via SAR backscatter increase ($\Delta\gamma^0 > +2\text{ to }+3\text{ dB}$), spatial texture variance, and proximity to drainage corridors.
  - Control test required: a same-orbit no-event pair must yield $\approx 0$ flood/debris.
- **L6 (AI Flood Segmentation Model - Parallel with L2)**:
  - Task: Segment flood water from Sentinel-1 pre/post. Input channels: pre VV/VH, post VV/VH, log-ratio, DEM slope.
  - Train on Kuro Siwo dataset split strictly BY EVENT/REGION (never random patches), keeping at least one Himalayan/mountainous event completely unseen.
  - Held-out test evaluation must report IoU, F1, precision, recall, and benchmark against an Otsu threshold baseline on the same scenes.
  - Generalization check: report metrics per region; document whether model beats baseline on unseen mountain scenes.
  - Inference function: `predict(pre_tif, post_tif, dem) -> flood_mask` usable on any bbox without place-specific tuning.
- **L3 (EMSR927 Validation)**: Resides strictly inside `validation/` to benchmark L2/L6 outputs against Copernicus EMS ground truth.
- **L4 (OSM Damage Grading)**:
  - Pass check: counts must reconcile with total OSM inventory within the AOI.
  - Output must report OSM coverage (total buildings, roads, bridges present in the AOI pre-event).
  - Sparse OSM resulting in low counts is a documented data limitation, not a software bug.
- **L5 (Cut-off Settlement & Routing)**:
  - If no hospital is tagged or reachable in OSM within the AOI/vicinity, automatically fall back to the nearest town/major place node and explicitly state this fallback in the output.
- **L7 (Dashboard & Bilingual SitRep)**: English and Nepali situation reports with 100% computed metrics and interactive map visualization.
- **L8 (Bonus Hydrological Flow Path)**: Downstream D8 flow tracing from arbitrary upstream source coordinate.
