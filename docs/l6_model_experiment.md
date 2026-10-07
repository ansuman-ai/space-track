# Layer 6 Model Experiment: KuroSiwo Sentinel-1 Flood Segmentation in the Himalayas

## 1. Executive Summary & Decision
- **Objective**: Evaluate whether the official pretrained KuroSiwo deep learning model improves Sentinel-1 flood segmentation on unseen, rugged Himalayan terrain (Trishuli 2026 and Melamchi 2021).
- **Outcome**: The stop rule was reached. Pretrained KuroSiwo SNUNet failed to detect flood inundation on Trishuli (IoU: 0.0001, F1: 0.0002) and Melamchi (IoU: 0.0000). The true S1-only threshold baseline similarly failed (IoU: 0.0008). Both S1 approaches fail because the radar signal change inside the flood polygon is only **-0.06 dB** due to turbulent whitewater scattering.
- **Decision**: **DO NOT MERGE** into the operational pipeline. Optical Sentinel-2 remains mandatory for flood/debris mapping in steep Himalayan valleys.

---

## 2. Model Checkpoint & Architecture
- **Checkpoint**: Official weights `best_segmentation.pt` (144.6 MB, Epoch 13) published by Orion-AI-Lab.
- **Architecture**: `SNUNet_ECAM` (Siamese DenseUNet with Ensemble Channel Attention Modules for Change Detection, `base_channel=32`, 3 classes: 0 = No Water, 1 = Permanent Water, 2 = Flooded Water).
- **Decision Rule**: Strict default `argmax(1)` logits (no post-hoc threshold tuning).

---

## 3. Preprocessing & Sensor Alignment
- **Input Pipeline**: Sentinel-1 Planetary Computer RTC $\gamma^0_{\text{dB}}$ converted to linear amplitude, clamped to $[0.0, 0.15]$, and normalized using KuroSiwo dataset statistics:
  $$\text{VV}_{\text{lin}} = \text{clip}(10^{\text{VV}_{\text{dB}}/10}, 0.0, 0.15), \quad \text{VH}_{\text{lin}} = \text{clip}(10^{\text{VH}_{\text{dB}}/10}, 0.0, 0.15)$$
  $$\mu_{\text{VV}} = 0.0953, \, \sigma_{\text{VV}} = 0.0427, \quad \mu_{\text{VH}} = 0.0264, \, \sigma_{\text{VH}} = 0.0215$$
- **Channel 3 Configuration**: Verified from official repository `configs/train/data_config.json` (`slope: true`); channel 3 feeds terrain slope normalized by $\mu=2.1277^\circ, \sigma=67.5048^\circ$. (Raw DEM elevation was not used in this checkpoint).
- **Remaining Mismatch**: RTC $\gamma^0$ vs ESA SNAP $\sigma^0$ radiometry, severe mountain layover/shadow geometry, and turbulent river whitewater vs calm floodplain specular reflection.

---

## 4. KuroSiwo Benchmark Sanity Check
Evaluated on 28 official test-split patches (1.4M pixels, 12 flooded / 16 dry scenes) with zero threshold tuning (`argmax`):
- **Our Run**: Flood F1 = **81.75%**, Flood IoU = **69.14%** (Precision = 84.92%, Recall = 78.82%).
- **Paper Benchmark**: Paper reported SNUNet GRD Flood F1 = **74.26%**, mIoU = **71.30%** (Table 2).
- **Conclusion**: Confirmed in the **same range as the paper**, verifying correct checkpoint loading and tensor routing.

---

## 5. Evaluation Results

### A. Trishuli Event Pair (2026-08-16 / 2026-08-28) vs EMSR927
Evaluated strictly against Copernicus EMS EMSR927 ground truth using `validation/verify_metrics.py`:

| Method | Modality | TP | FP | FN | Precision | Recall | F1 | IoU |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **KuroSiwo SNUNet (Argmax)** | S1 SAR only | 1 | 0 | 11,100 | 1.0000 | 0.0001 | 0.0002 | **0.0001** |
| **Adaptive S1 Baseline (`water.py`)** | S1 SAR only | 9 | 0 | 11,092 | 1.0000 | 0.0008 | 0.0016 | **0.0008** |
| **Relaxed S1 Log-Ratio ($\Delta\text{VV} < -2\text{ dB}$)** | S1 SAR only | 750 | 456 | 10,351 | 0.6219 | 0.0676 | 0.1219 | **0.0649** |
| **Multi-Orbit S1 ($z < -3 \lor \text{O19} < -2.5\text{ dB}$)** | S1 SAR only | 1,168 | 558 | 9,933 | 0.6767 | 0.1052 | 0.1821 | **0.1002** |
| **Pipeline Ablation A (L2.2 variant)** | S2 + S1 | 6,527 | 2,253 | 4,574 | 0.7434 | 0.5880 | 0.6566 | **0.4888** |
| **Pipeline Final Map (L2.5)** | S2 + S1 | 6,591 | 295 | 4,510 | 0.9572 | 0.5937 | 0.7329 | **0.5784** |

### B. Trishuli No-Event (2026-03-15)
- **False-Positive Area**: **0.000200 km²** (2 pixels out of 2,015,013 valid pixels).
- **Evaluation**: Satisfies the near-zero requirement.

### C. Melamchi Flash Flood (2021-06-15) Agreement
*(Unseen event; agreement with S2 optical baseline, not accuracy)*:
- Model predicted only 2 flood pixels across the entire valley.
- Agreement vs S2 observed flood (Class 2, 17,432 px): $\text{IoU} = \mathbf{0.0000}$ (TP: 0).
- Agreement vs S2 total affected (Classes 2+3, 54,658 px): $\text{IoU} = \mathbf{0.000018}$ (TP: 1).

---

## 6. Physical Root Cause: The -0.06 dB SAR Signal Void
Statistical extraction across the 11,101 EMSR927 ground-truth flood pixels reveals why all S1-only methods fail:
- $\text{Pre-event VV}$: $-7.331\text{ dB}$
- $\text{Post-event VV}$: $-7.390\text{ dB}$
- **Net Change $\Delta\text{VV}$**: **$-0.0585\text{ dB}$ ($\approx -0.06\text{ dB}$)**
- **Net Change $\Delta\text{VH}$**: **$-0.864\text{ dB}$**

**Physical Explanation**:
KuroSiwo was trained predominantly on lowland, low-gradient river plains (e.g., Terai, Po, Mississippi) where inundation creates calm, flat water surfaces causing strong specular reflection and severe backscatter drops ($\le -18\text{ dB}$, $\Delta\sigma^0 \le -6\text{ to } -10\text{ dB}$). In contrast, Himalayan flash floods flow through steep, narrow mountain gorges as hyper-turbulent torrents with boulders, debris, and standing waves. This rough water surface exhibits diffuse radar backscatter nearly identical to gravel beds and dry terrain ($-7.3\text{ dB}$). Neither deep Siamese networks nor radiometric thresholding can segment water when the electromagnetic contrast does not exist. Optical Sentinel-2 indices ($\Delta\text{NDVI}$, $\Delta\text{BSI}$) remain essential.

---

## 7. Citation
```bibtex
@inproceedings{NEURIPS2024_43612b06,
  author    = {Bountos, Nikolaos Ioannis and Sdraka, Maria and Zavras, Angelos and Karavias, Andreas and Karasante, Ilektra and Herekakis, Themistocles and Thanasou, Angeliki and Michail, Dimitrios and Papoutsis, Ioannis},
  booktitle = {Advances in Neural Information Processing Systems (NeurIPS)},
  editor    = {A. Globerson and L. Mackey and D. Belgrave and A. Fan and U. Paquet and J. Tomczak and C. Zhang},
  pages     = {38105--38121},
  publisher = {Curran Associates, Inc.},
  title     = {Kuro Siwo: 33 billion m\textasciicircum 2 under the water. A global multi-temporal satellite dataset for rapid flood mapping},
  url       = {https://proceedings.neurips.cc/paper_files/paper/2024/file/43612b0662cb6a4986edf859fd6ebafe-Paper-Datasets_and_Benchmarks_Track.pdf},
  volume    = {37},
  year      = {2024}
}
```
