# CHANGELOG: Key Verification Numbers and Audit Trail

## Baseline Status (v1.1.0 Freeze)

### Bit-for-Bit L2 & L4 Invariance (Test A & Test B)
All Layer 2 flood hazard masks and Layer 4 infrastructure damage assessments remain 100% byte-identical:
- **Test A (Trishuli Flash Flood 2026)**:
  - `hazard_classes.tif`: `6a0e1810c8a85f35149943b4408142ba`
  - `l2_summary.json`: `e2305ab983361443f517c1fbabeef924`
  - `quicklook_layer2.png`: `8175f1d18b434defdd60f65b1c8767b3`
  - `buildings_graded.geojson`: `b516c42d2a71aaed5eac5cfe76c4ecf8`
  - `roads_graded.geojson`: `1c5a2a58f9c57d00f227751b3478136d`
  - `bridges_graded.geojson`: `253d3f75b85607791b87011e231c781c`
  - `quicklook_l4.png`: `b7d771fb5c8379fb1c19e344ff60a569`
  - Buildings Assessed: 225 affected (107 destroyed, 42 damaged, 76 possibly damaged)
  - Bridges Assessed: 13 affected (12 destroyed, 1 possibly damaged)
  - Roads Assessed: 5.98 km destroyed, 4.39 km possibly damaged, 32.21 km cloud-unverified

- **Test B (Melamchi Debris Flow 2021)**:
  - `hazard_classes.tif`: `2898844a273f0e146dc6ae34f9fcae47`
  - `l2_summary.json`: `85d638387a82d1e745bcd91931886670`
  - `quicklook_layer2.png`: `40050b37d14955730fb804e027508666`
  - `buildings_graded.geojson`: `5fc5472dc4d03c81d5f19725bc28e1a6`
  - `roads_graded.geojson`: `a6105d195155764966f876d7fe40a591`
  - `bridges_graded.geojson`: `a192dc523de0f8214e3d7366074c3494`
  - `quicklook_l4.png`: `5db0df7d7462456a1512320fbab3a24e`
  - Buildings Assessed: 87 affected (72 destroyed, 15 possibly damaged)
  - Bridges Assessed: 11 affected (4 destroyed, 7 possibly damaged)
  - Roads Assessed: 13.92 km destroyed, 14.88 km possibly damaged, 0.0 km cloud-unverified

---

## Part 2 Problem-Statement Destination Compliance (30 km Buffer Towns/Cities)

Adding `place=town/city` inside the 30 km pre-event buffer to health facilities updated the Layer 5 reachability destinations:
- **Test A (Trishuli)**:
  - Destination Count: 34 -> **39** (+5 towns)
  - Vehicle cut-off count (opt/pess): 44 -> **44** / 44 -> **44**
  - Walking cut-off count (opt/pess): 4 -> **4** / 4 -> **4**
  - No ground access count (opt/pess): 4 -> **4** / 4 -> **4**
  - Top repair package: 19 settlements reconnected, 939 buildings, 4 elements (unchanged)
  - **Best Single Repair Evolution**:
    - `processed/routing/repair_priority.json`: Best single repair is now `way/248705796` (primary, 264.9 m destroyed) reconnecting **2 settlements** and **38 buildings**. The prior statement *"No single repair reconnects a settlement"* is FALSE for Trishuli.
  - **Repair Package 2 Evolution**:
    - `processed/routing/repair_packages.json`: Package 2 is now **4 elements** (`way/245248456`, `way/248705796`, `way/342026948`, `way/784420806`) reconnecting **9 settlements** and **213 buildings** (previously 9 elements). Package 1 remains unchanged: 4 elements (`way/84566285`, `way/245248450`, `way/332122791`, `way/1266396385`) reconnecting 19 settlements and 939 buildings.

- **Test B (Melamchi)**:
  - Destination Count: 585 -> **610** (+25 towns)
  - Vehicle cut-off count (opt/pess): 5 -> **5** / 16 -> **16**
  - Walking cut-off count (opt/pess): 6 -> **6** / 16 -> **16**
  - No ground access count (opt/pess): 5 -> **5** / 13 -> **13**
  - Top repair package: 2 settlements reconnected, 17 buildings, 1 element (unchanged)

---

## Situation Report & Copilot Verification

1. **One-Page PDF Constraint**:
   - Both English and Nepali sitreps fit strictly on exactly 1 A4 portrait page across all disaster runs (Trishuli, Melamchi, Chamoli, Assam). Verified via `pdfinfo`.
   - 0 hardcoded numbers or developer notes in `sitrep.py`.
2. **Attributions & Prototype Disclaimers**:
   - European Union Copernicus Emergency Management Service data (EMSR927, EMSR692, EMSR659) credited.
   - *"Educational prototype, not an operational tool."* displayed in dashboard footer, sitrep, and documentation.
3. **Copilot Correctness**:
   - 100/100 automated checks passed in `check_dashboard_data.py`.
   - 15/15 held-out evaluations passed in live server testing.
   - 13/13 unit and security audit tests passed in `pytest`.
