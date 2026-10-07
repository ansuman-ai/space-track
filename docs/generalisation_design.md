# Terrain-Adaptive Inundation Architecture: Generalisation Design

## 1. Motivation
The steep-valley pipeline (`e2e-final2`) accurately models high-relief Himalayan events (Trishuli, Melamchi, Sikkim Teesta GLOF) where flooding and debris flows are confined to narrow canyons with steep valley walls. In such terrain, D8 drainage accumulation and strict 100 m stream-proximity filtering eliminate radar layover/shadow false alarms.
However, in flat plains (e.g., Brahmaputra, Assam), low hydraulic gradients cause D8 routing to fail (generating artificial, disconnected stream cells), while floodwaters expand kilometers beyond active channels. Under 100% monsoon cloud cover, requiring 100 m stream proximity eliminates all real flood signals (~30% of the Assam grid).

A terrain-adaptive architecture bifurcates processing into:
1. **Steep Mountain Valleys**: Bit-for-bit identical to `e2e-final2` baseline.
2. **Flat Floodplains**: Wide-area SAR specular water detection and optical MNDWI expansion without stream-proximity pruning.

---

## 2. Terrain Classification (Steep Valley vs. Flat Floodplain)
Terrain regime is classified automatically per study area from the DEM slope and Height Above Nearest Drainage (HAND):

$$\text{Regime} = \begin{cases} 
\text{flat\_floodplain}, & \text{if } \text{median}(\text{slope}) < 8.0^\circ \text{ and } P(\text{slope} < 5^\circ) > 0.40 \text{ and } P(\text{HAND} \le 15\text{ m}) > 0.50 \\
\text{steep\_valley}, & \text{otherwise}
\end{cases}$$

### Empirical Terrain Metrics
| Area | Median Slope | $P(\text{Slope} < 5^\circ)$ | Median HAND | $P(\text{HAND} \le 15\text{ m})$ | Classification |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Trishuli (A)** | $33.3^\circ$ | $0.41\%$ | $317.1\text{ m}$ | $5.71\%$ | **Steep Valley** |
| **Melamchi (B)** | $28.4^\circ$ | $0.62\%$ | $285.4\text{ m}$ | $7.12\%$ | **Steep Valley** |
| **Sikkim (GLOF)** | $37.4^\circ$ | $0.46\%$ | $326.0\text{ m}$ | $6.16\%$ | **Steep Valley** |
| **Assam (Plains)** | $0.76^\circ$ | $84.24\%$ | $0.00\text{ m}$ | $96.91\%$ | **Flat Floodplain** |

When classified as `steep_valley`, the execution path is strictly preserved, guaranteeing 100% byte-identical reproduction of Test A and Test B outputs.

---

## 3. Flat-Floodplain Detection Path

### A. Sentinel-1 SAR Open-Water Flood Detection
On flat terrain, calm open water acts as a specular reflector, resulting in low backscatter in post-event VV ($\sigma^0_{\text{VV}} < \tau_{\text{water}}$) and significant attenuation relative to pre-event backscatter ($\Delta\sigma^0_{\text{VV}} = \sigma^0_{\text{post}} - \sigma^0_{\text{pre}} < \tau_{\text{diff}}$):
1. **Water Level Threshold ($\tau_{\text{water}}$)**: Derived from Otsu thresholding on post-event VV if bimodal within the floodplain; bounded by physical water limits ($-18.0\text{ dB} \le \tau_{\text{water}} \le -13.0\text{ dB}$).
2. **Attenuation Threshold ($\tau_{\text{diff}}$)**: Calibrated against the control pre/post pair inside the floodplain to ensure $0\%$ false alarms on dry control/no-event dates (guarded by floor $\tau_{\text{diff}} \le -3.0\text{ dB}$).
3. **Permanent Water Subtraction**: Pre-event permanent water (Class 1, derived from pre-event NDWI and OSM) is excluded so that only newly inundated floodwaters are tagged.
4. **Floodplain HAND Constraint**: Flooding is constrained to hydrologically feasible elevations ($\text{HAND} \le 15.0\text{ m}$).
5. **No Stream Proximity Filter**: Disconnected from synthetic D8 stream centerlines.
6. **Sub-label**: Class 2 hazard polygons are attributed with `sub_label: "flood water"`.

### B. Sentinel-2 Optical Integration (When Clear)
Where optical pixels are valid ($S_2\text{ valid}$), open water is detected via modified normalised difference water index:
$$\text{MNDWI}_{\text{post}} > 0.0 \quad \text{AND} \quad \Delta\text{MNDWI} = \text{MNDWI}_{\text{post}} - \text{MNDWI}_{\text{pre}} > 0.15$$
Optical water detections merge with SAR flood detections.

---

## 4. Layer 4 Building Grading Under SAR Evidence
In flat areas where optical imagery is obscured by persistent clouds:
- Buildings intersecting Class 2 flood polygons (or within $10\text{ m}$) are graded **Destroyed** / **Damaged** / **Possibly Damaged** from SAR evidence.
- Buildings outside the flood polygon in SAR-monitored zones are graded **Not Affected** (with `evidence: "sar-clear"`), rather than defaulting to `"Unknown (cloud)"`.

---

## 5. AI Model Integration (KuroSiwo SNUNet)
The pretrained KuroSiwo `SNUNet_ECAM` (from `l6-model`) is integrated as an alternative detector on flat floodplains. Both the threshold detector and SNUNet are evaluated against validation flood extents (Copernicus EMS / UNOSAT) to adopt the superior approach.
