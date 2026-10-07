# Kuro Siwo SNUNet Evaluation & Benchmark Report

## 1. Overview & Architecture
The **Kuro Siwo** pretrained deep learning model is a Siamese Nested U-Net (SNUNet) architecture trained on multi-temporal Sentinel-1 C-band Synthetic Aperture Radar (SAR) backscatter (VV and VH polarizations) along with Copernicus DEM slope. It predicts binary and multi-class disaster hazard masks (Class 0: Intact, Class 1: Pre-existing Permanent Water, Class 2: Flood / Debris Hazard).

In this project, Kuro Siwo was evaluated as an AI candidate detector for flat floodplain inundation mapping and compared against our physics-based multi-sensor (Sentinel-1 RTC + Sentinel-2 MSI) threshold detector.

---

## 2. Experimental Benchmark Results

### 2.1 Official Copernicus EMS Validation (Flat Floodplains)

All evaluations below were performed strictly within official Copernicus EMS Area of Interest (AOI) boundaries on frame-matched Sentinel-1 pairs ($\ge 90\%$ bbox overlap, identical relative orbit):

| Benchmark Event / Site | Detector Variant | Detected Area ($\text{km}^2$) | EMS GT Area ($\text{km}^2$) | IoU | F1 Score | Precision | Recall | No-Event False Alarm ($\text{km}^2$) | Safety Status ($< 0.07\text{ km}^2$) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Greece Storm Daniel**<br>*(EMSR692 AOI02, Thessaly Plain)* | **Combined S1+S2 (Default)** | **$537.66$** | $560.80$ | **$0.4159$** | **$0.5875$** | $0.6001$ | **$0.5754$** | **$0.0000$** | **PASS (SELECTED)** |
| | **S1-Threshold Only** | $67.34$ | $560.80$ | $0.1157$ | $0.2073$ | **$0.9671$** | $0.1161$ | **$0.0000$** | PASS |
| | **Kuro Siwo SNUNet** | $84.23$ | $560.80$ | $0.1403$ | $0.2461$ | $0.9424$ | $0.1415$ | **$234.83$** | **FATAL FAIL (235 $\text{km}^2$)** |
| **Italy Emilia-Romagna**<br>*(EMSR659 AOI01, Conselice / Ravenna)* | **Combined S1+S2 (Default)** | **$10.65$** | $16.32$ | **$0.2127$** | **$0.3508$** | $0.3922$ | **$0.3173$** | **$0.0366$** | **PASS (SELECTED)** |
| | **S1-Threshold Only** | $10.63$ | $16.32$ | $0.2130$ | $0.3511$ | $0.3931$ | $0.3173$ | **$0.0366$** | PASS |
| | **Kuro Siwo SNUNet** | $10.56$ | $16.32$ | $0.1825$ | $0.3087$ | $0.3468$ | $0.2781$ | $0.0405$ | PASS |

---

### 2.2 Mountain Debris Flow Events

| Mountain Event | Kuro Siwo Observed Area | Pipeline Physics Observed Area | EMS / Ground Truth Alignment |
| :--- | :---: | :---: | :--- |
| **Test A: Trishuli Gorkha Debris Flow** (EMSR927) | $0.16\text{ km}^2$ | $1.08\text{ km}^2$ | Misses narrow lateral debris channels; SNUNet relies on flat specular water reflection, failing on steep turbulent torrents. |
| **Test B: Melamchi Outburst Flood** (2021) | $0.22\text{ km}^2$ | $0.90\text{ km}^2$ | Captures only the main downstream gravel bar, missing upstream scouring and mid-valley infrastructure cuts. |

---

## 3. Why Kuro Siwo Is NOT the Default

1. **Catastrophic False Alarm Rate on Mediterranean Dry Terrain**:
   During the Greece dry summer no-event test (August 2023), Kuro Siwo triggered **$234.83\text{ km}^2$ of false positive flood hazard**. This exceeds our strict safety criterion ($< 0.07\text{ km}^2$) by over **3,300x**.
2. **Double-Bounce Inundation Blindness**:
   On flat agricultural floodplains (e.g. Thessaly Plain), floodwater beneath standing crops produces double-bounce backscatter increases rather than specular reflection dips. Kuro Siwo's C-band SAR features achieve only **$14.15\%$ recall**, missing $>470\text{ km}^2$ of inundated farmland that Sentinel-2 optical readily detects via $\Delta\text{MNDWI}$ and NIR attenuation.
3. **Multi-Sensor Superiority**:
   Our physics-based **Combined S1+S2** detector achieves **$\text{F1} = 0.5875$** (IoU $0.4159$, Recall $57.5\%$) on Greece with **$0.0000\text{ km}^2$** false alarms on the no-event test, clearly outperforming Kuro Siwo.

---

## 4. Usage as Optional Experimental Detector

Kuro Siwo is retained as an optional plug-in for research and experimental benchmarking:
- **Configuration**: Set `detector: "kurosiwo"` in the configuration YAML or pass `--config` with `detector: kurosiwo`. Default is `detector: "combined"`.
- **Validation Status**: When `detector: "kurosiwo"` is active, all outputs automatically carry `"validation_status": "experimental, not validated"`.
