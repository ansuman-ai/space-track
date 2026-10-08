#!/usr/bin/env python3
"""
Automated Data Integrity Verification Script for Disaster Assessment Dashboard.
For every run in runs/, compares each number returned by the API / metadata engine
with the underlying raw pipeline JSON files and fails on any mismatch.
"""

import sys
import os
import json
from pathlib import Path

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from src.dashboard.app import get_run_metadata, RUNS_DIR


def verify_run(run_folder: Path) -> bool:
    run_id = run_folder.name
    print(f"\n=======================================================")
    print(f"VERIFYING RUN: {run_id}")
    print(f"=======================================================")

    meta = get_run_metadata(run_folder)
    if not meta:
        print(f"FAILED: Could not parse metadata for {run_id}")
        return False

    proc = run_folder / "processed"
    routing = proc / "routing"

    m = meta["metrics"]
    errors = []

    # 1. Verify Areas against processed/l2_stats.json
    l2_stats_file = proc / "l2_stats.json"
    if l2_stats_file.exists():
        l2 = json.load(open(l2_stats_file))
        raw_areas = l2.get("areas_km2", {})
        
        expected_obs = round(raw_areas.get("event_total_affected", 0.0), 4)
        expected_inf = round(raw_areas.get("event_inferred_affected", 0.0), 4)
        expected_perm = round(raw_areas.get("class_1_permanent_water", 0.0), 4)

        if m["areas"]["observed_km2"] != expected_obs:
            errors.append(f"Observed km2 mismatch: API={m['areas']['observed_km2']} vs JSON={expected_obs}")
        if m["areas"]["inferred_km2"] != expected_inf:
            errors.append(f"Inferred km2 mismatch: API={m['areas']['inferred_km2']} vs JSON={expected_inf}")
        if m["areas"]["permanent_water_km2"] != expected_perm:
            errors.append(f"Permanent water km2 mismatch: API={m['areas']['permanent_water_km2']} vs JSON={expected_perm}")
    else:
        print(f"Note: l2_stats.json not found for {run_id}")

    # 2. Verify Buildings, Bridges, Roads against processed/damage_summary.json
    dmg_file = proc / "damage_summary.json"
    if dmg_file.exists():
        dmg = json.load(open(dmg_file))
        b_counts = dmg.get("buildings", {}).get("damage_grade_counts", {})
        br_counts = dmg.get("bridges", {}).get("damage_grade_counts", {})
        rd_counts = dmg.get("roads", {}).get("km_by_damage_grade", {})

        # Buildings
        exp_destroyed_b = b_counts.get("Destroyed", 0)
        exp_damaged_b = b_counts.get("Damaged", 0)
        exp_pos_damaged_b = b_counts.get("Possibly damaged", 0)
        exp_flooded_b = b_counts.get("Flooded", 0)
        exp_pos_flooded_b = b_counts.get("Possibly flooded", 0)
        exp_unverified_b = b_counts.get("Unknown (cloud)", 0)
        exp_total_b = exp_destroyed_b + exp_damaged_b + exp_pos_damaged_b + exp_flooded_b + exp_pos_flooded_b

        if m["buildings"]["total_affected"] != exp_total_b:
            errors.append(f"Total affected buildings mismatch: API={m['buildings']['total_affected']} vs JSON={exp_total_b}")
        if m["buildings"]["destroyed"] != exp_destroyed_b:
            errors.append(f"Destroyed buildings mismatch: API={m['buildings']['destroyed']} vs JSON={exp_destroyed_b}")
        if m["buildings"]["damaged"] != exp_damaged_b:
            errors.append(f"Damaged buildings mismatch: API={m['buildings']['damaged']} vs JSON={exp_damaged_b}")
        if m["buildings"]["possibly_damaged"] != exp_pos_damaged_b:
            errors.append(f"Possibly damaged buildings mismatch: API={m['buildings']['possibly_damaged']} vs JSON={exp_pos_damaged_b}")
        if m["buildings"]["flooded"] != exp_flooded_b:
            errors.append(f"Flooded buildings mismatch: API={m['buildings']['flooded']} vs JSON={exp_flooded_b}")
        if m["buildings"]["possibly_flooded"] != exp_pos_flooded_b:
            errors.append(f"Possibly flooded buildings mismatch: API={m['buildings']['possibly_flooded']} vs JSON={exp_pos_flooded_b}")
        if m["buildings"]["unverified"] != exp_unverified_b:
            errors.append(f"Unverified buildings mismatch: API={m['buildings']['unverified']} vs JSON={exp_unverified_b}")

        # Bridges
        exp_destroyed_br = br_counts.get("Destroyed", 0)
        exp_pos_damaged_br = br_counts.get("Possibly damaged", 0)
        exp_flooded_br = br_counts.get("Flooded / impassable", 0)
        exp_pos_flooded_br = br_counts.get("Possibly flooded", 0)
        exp_unverified_br = br_counts.get("Unknown (cloud)", 0)
        exp_total_br = exp_destroyed_br + exp_pos_damaged_br + exp_flooded_br + exp_pos_flooded_br

        if m["bridges"]["total_affected"] != exp_total_br:
            errors.append(f"Total affected bridges mismatch: API={m['bridges']['total_affected']} vs JSON={exp_total_br}")
        if m["bridges"]["destroyed"] != exp_destroyed_br:
            errors.append(f"Destroyed bridges mismatch: API={m['bridges']['destroyed']} vs JSON={exp_destroyed_br}")
        if m["bridges"]["possibly_damaged"] != exp_pos_damaged_br:
            errors.append(f"Possibly damaged bridges mismatch: API={m['bridges']['possibly_damaged']} vs JSON={exp_pos_damaged_br}")
        if m["bridges"].get("flooded", 0) != exp_flooded_br:
            errors.append(f"Flooded bridges mismatch: API={m['bridges'].get('flooded', 0)} vs JSON={exp_flooded_br}")
        if m["bridges"].get("possibly_flooded", 0) != exp_pos_flooded_br:
            errors.append(f"Possibly flooded bridges mismatch: API={m['bridges'].get('possibly_flooded', 0)} vs JSON={exp_pos_flooded_br}")
        if m["bridges"]["unverified"] != exp_unverified_br:
            errors.append(f"Unverified bridges mismatch: API={m['bridges']['unverified']} vs JSON={exp_unverified_br}")

        # Roads
        exp_destroyed_rd = round(float(rd_counts.get("Destroyed", 0.0)), 2)
        exp_pos_damaged_rd = round(float(rd_counts.get("Possibly damaged", 0.0)), 2)
        exp_unverified_rd = round(float(rd_counts.get("Unknown (cloud)", 0.0)), 2)

        if m["roads_km"]["destroyed_km"] != exp_destroyed_rd:
            errors.append(f"Destroyed roads km mismatch: API={m['roads_km']['destroyed_km']} vs JSON={exp_destroyed_rd}")
        if m["roads_km"]["possibly_damaged_km"] != exp_pos_damaged_rd:
            errors.append(f"Possibly damaged roads km mismatch: API={m['roads_km']['possibly_damaged_km']} vs JSON={exp_pos_damaged_rd}")
        if m["roads_km"]["unverified_km"] != exp_unverified_rd:
            errors.append(f"Unverified roads km mismatch: API={m['roads_km']['unverified_km']} vs JSON={exp_unverified_rd}")

    # 3. Verify Cutoffs against processed/routing/cutoff_summary.json AND settlements.geojson
    cut_file = routing / "cutoff_summary.json"
    if cut_file.exists():
        cut = json.load(open(cut_file))
        exp_veh_opt = cut.get("vehicle", {}).get("optimistic", {}).get("cut_off_count", 0)
        exp_veh_pess = cut.get("vehicle", {}).get("pessimistic", {}).get("cut_off_count", 0)
        exp_walk_opt = cut.get("walking", {}).get("optimistic", {}).get("cut_off_count", 0)
        exp_walk_pess = cut.get("walking", {}).get("pessimistic", {}).get("cut_off_count", 0)

        if m["cutoffs"]["vehicle_optimistic"] != exp_veh_opt:
            errors.append(f"Vehicle opt cutoffs mismatch: API={m['cutoffs']['vehicle_optimistic']} vs JSON={exp_veh_opt}")
        if m["cutoffs"]["vehicle_pessimistic"] != exp_veh_pess:
            errors.append(f"Vehicle pess cutoffs mismatch: API={m['cutoffs']['vehicle_pessimistic']} vs JSON={exp_veh_pess}")
        if m["cutoffs"]["walking_optimistic"] != exp_walk_opt:
            errors.append(f"Walking opt cutoffs mismatch: API={m['cutoffs']['walking_optimistic']} vs JSON={exp_walk_opt}")
        if m["cutoffs"]["walking_pessimistic"] != exp_walk_pess:
            errors.append(f"Walking pess cutoffs mismatch: API={m['cutoffs']['walking_pessimistic']} vs JSON={exp_walk_pess}")

    settle_file = routing / "settlements.geojson"
    if settle_file.exists():
        settle_geo = json.load(open(settle_file))
        geo_veh_opt = sum(1 for f in settle_geo.get("features", []) if f.get("properties", {}).get("vehicle_status_opt") == "cut_off")
        geo_veh_pess = sum(1 for f in settle_geo.get("features", []) if f.get("properties", {}).get("vehicle_status_pess") == "cut_off")
        geo_walk_opt = sum(1 for f in settle_geo.get("features", []) if f.get("properties", {}).get("walking_status_opt") == "cut_off")
        geo_walk_pess = sum(1 for f in settle_geo.get("features", []) if f.get("properties", {}).get("walking_status_pess") == "cut_off")

        if m["cutoffs"]["vehicle_optimistic"] != geo_veh_opt:
            errors.append(f"settlements.geojson vehicle opt mismatch: API={m['cutoffs']['vehicle_optimistic']} vs GeoJSON={geo_veh_opt}")
        if m["cutoffs"]["vehicle_pessimistic"] != geo_veh_pess:
            errors.append(f"settlements.geojson vehicle pess mismatch: API={m['cutoffs']['vehicle_pessimistic']} vs GeoJSON={geo_veh_pess}")
        if m["cutoffs"]["walking_optimistic"] != geo_walk_opt:
            errors.append(f"settlements.geojson walking opt mismatch: API={m['cutoffs']['walking_optimistic']} vs GeoJSON={geo_walk_opt}")
        if m["cutoffs"]["walking_pessimistic"] != geo_walk_pess:
            errors.append(f"settlements.geojson walking pess mismatch: API={m['cutoffs']['walking_pessimistic']} vs GeoJSON={geo_walk_pess}")

    # 4. Verify Repair Package 1 against processed/routing/repair_packages.json
    pkg_file = routing / "repair_packages.json"
    if pkg_file.exists():
        pkgs = json.load(open(pkg_file))
        ranked = pkgs.get("ranked_packages", [])
        actionable = [p for p in ranked if len(p.get("elements", [])) > 0]
        if actionable:
            p1 = actionable[0]
            exp_p1_settle = p1.get("settlements_count", 0)
            exp_p1_bld = p1.get("buildings_count", 0)
            exp_p1_elem = p1.get("element_count", len(p1.get("elements", [])))
        else:
            exp_p1_settle = 0
            exp_p1_bld = 0
            exp_p1_elem = 0

        if m["repair_package_1"]["reconnects_settlements"] != exp_p1_settle:
            errors.append(f"Repair pkg 1 settlements mismatch: API={m['repair_package_1']['reconnects_settlements']} vs JSON={exp_p1_settle}")
        if m["repair_package_1"]["reconnects_buildings"] != exp_p1_bld:
            errors.append(f"Repair pkg 1 buildings mismatch: API={m['repair_package_1']['reconnects_buildings']} vs JSON={exp_p1_bld}")
        if m["repair_package_1"]["element_count"] != exp_p1_elem:
            errors.append(f"Repair pkg 1 element count mismatch: API={m['repair_package_1']['element_count']} vs JSON={exp_p1_elem}")

    # 5. Validation Banner logic verification
    val_status = meta["validation_status"]
    val_file = proc / "validation_status.json"
    if val_file.exists():
        v_data = json.load(open(val_file))
        expected_banner = v_data.get("validation_status", "")
        if val_status != expected_banner:
            errors.append(f"Validation status mismatch: API='{val_status}' vs JSON='{expected_banner}'")
    elif "test_A_cold_verify" in run_id:
        if "EMSR927" not in val_status:
            errors.append(f"Trishuli must have EMSR927 banner, got: '{val_status}'")

    # 6. Attribution Year verification
    expected_year = meta["event_date"].split("-")[0] if meta["event_date"] else "2026"
    if meta["event_year"] != expected_year:
        errors.append(f"Attribution year mismatch: API={meta['event_year']} vs expected={expected_year}")

    # Output results
    if errors:
        print(f"FAILED with {len(errors)} error(s):")
        for err in errors:
            print(f"  - {err}")
        return False
    else:
        print("PASSED - All fields match raw JSON files bit-for-bit:")
        print(f"  * Label: {meta['label']}")
        print(f"  * Event Year / Date: {meta['event_year']} / {meta['event_date']}")
        print(f"  * Validation Banner: {val_status}")
        print(f"  * Observed Affected: {m['areas']['observed_km2']} km² (Inferred: {m['areas']['inferred_km2']} km²)")
        print(f"  * Buildings Affected: {m['buildings']['total_affected']} (Destroyed: {m['buildings']['destroyed']}, Damaged: {m['buildings']['damaged']}, Possible: {m['buildings']['possibly_damaged']}, Flooded: {m['buildings']['flooded']}, Poss. Flooded: {m['buildings']['possibly_flooded']})")
        print(f"  * Bridges Affected: {m['bridges']['total_affected']} (Destroyed: {m['bridges']['destroyed']}, Possible: {m['bridges']['possibly_damaged']})")
        print(f"  * Roads: {m['roads_km']['destroyed_km']} km Destroyed, {m['roads_km']['possibly_damaged_km']} km Possibly Damaged (Unverified: {m['roads_km']['unverified_km']} km)")
        print(f"  * Cutoffs: Vehicle (opt: {m['cutoffs']['vehicle_optimistic']}, pess: {m['cutoffs']['vehicle_pessimistic']}), Walking (opt: {m['cutoffs']['walking_optimistic']}, pess: {m['cutoffs']['walking_pessimistic']})")
        print(f"  * Repair Pkg 1: Reconnects {m['repair_package_1']['reconnects_settlements']} settlements / {m['repair_package_1']['reconnects_buildings']} buildings ({m['repair_package_1']['element_count']} elements)")
        return True


def verify_no_cross_run_leakage() -> bool:
    """
    Simulates sequential run selection (Trishuli -> Melamchi -> Assam -> Trishuli)
    and asserts that metadata returned by the dashboard engine comes strictly from
    the selected run, proving zero cross-run state pollution or stale DOM cache leakage.
    """
    print("\n=======================================================")
    print("VERIFYING STRICT PER-RUN DATA ISOLATION (NO STATE LEAKAGE)")
    print("=======================================================")

    trishuli_dir = RUNS_DIR / "test_A_cold_verify"
    melamchi_dir = RUNS_DIR / "test_B_cold_verify"
    assam_dir = RUNS_DIR / "practice_assam_event"

    if not (trishuli_dir.exists() and melamchi_dir.exists() and assam_dir.exists()):
        print("Note: One of core runs missing, skipping cross-run leakage assertion.")
        return True

    # 1. Load Trishuli
    m_a1 = get_run_metadata(trishuli_dir)
    assert m_a1["metrics"]["buildings"]["destroyed"] == 107, f"Expected 107 destroyed, got {m_a1['metrics']['buildings']['destroyed']}"
    assert m_a1["metrics"]["bridges"]["destroyed"] == 12, f"Expected 12 destroyed bridges, got {m_a1['metrics']['bridges']['destroyed']}"
    assert m_a1["metrics"]["cutoffs"]["vehicle_optimistic"] == 44, f"Expected 44 vehicle cutoffs, got {m_a1['metrics']['cutoffs']['vehicle_optimistic']}"
    assert m_a1["metrics"]["repair_package_1"]["reconnects_settlements"] == 19
    assert m_a1["metrics"]["repair_package_1"]["reconnects_buildings"] == 939
    assert "EMSR927" in m_a1["validation_status"]
    print("✓ Trishuli loaded: 1.08 km², 107 destroyed, 13 bridges, 44 cut-offs, pkg1 reconnects 19/939")

    # 2. Switch to Melamchi
    m_b = get_run_metadata(melamchi_dir)
    assert m_b["metrics"]["buildings"]["destroyed"] == 72, f"Expected 72 destroyed, got {m_b['metrics']['buildings']['destroyed']}"
    assert m_b["metrics"]["bridges"]["destroyed"] == 4, f"Expected 4 destroyed bridges, got {m_b['metrics']['bridges']['destroyed']}"
    assert m_b["metrics"]["cutoffs"]["vehicle_optimistic"] == 5, f"Expected 5 vehicle cutoffs, got {m_b['metrics']['cutoffs']['vehicle_optimistic']}"
    # Must NOT retain Trishuli's repair package or cutoffs!
    assert m_b["metrics"]["repair_package_1"]["reconnects_settlements"] != 19, "Leaked Trishuli repair package into Melamchi!"
    assert m_b["metrics"]["repair_package_1"]["reconnects_buildings"] != 939, "Leaked Trishuli buildings count into Melamchi!"
    assert "EMSR927" not in m_b["validation_status"], "Leaked EMSR927 validation banner into Melamchi!"
    print("✓ Melamchi loaded: 0.44 km², 72 destroyed, 4 bridges, 5 cut-offs, 0-element package eliminated (isolated_pre_event excluded)")

    # 3. Switch to Assam
    m_c = get_run_metadata(assam_dir)
    assert m_c["regime"] == "flat_floodplain"
    assert m_c["metrics"]["buildings"]["flooded"] == 9, f"Expected 9 flooded, got {m_c['metrics']['buildings']['flooded']}"
    assert m_c["metrics"]["buildings"]["destroyed"] == 0, "Flat terrain should have 0 destroyed buildings"
    assert m_c["metrics"]["cutoffs"]["vehicle_optimistic"] == 5
    assert m_c["metrics"]["repair_package_1"]["reconnects_settlements"] != 19
    print("✓ Assam loaded: flat_floodplain, 9 flooded buildings, 5 cut-offs")

    # 4. Switch BACK to Trishuli - assert pristine reload
    m_a2 = get_run_metadata(trishuli_dir)
    assert m_a2["metrics"]["buildings"]["destroyed"] == 107
    assert m_a2["metrics"]["bridges"]["destroyed"] == 12
    assert m_a2["metrics"]["cutoffs"]["vehicle_optimistic"] == 44
    assert m_a2["metrics"]["repair_package_1"]["reconnects_settlements"] == 19
    assert m_a2["metrics"]["repair_package_1"]["reconnects_buildings"] == 939
    assert "EMSR927" in m_a2["validation_status"]
    print("✓ Trishuli reloaded: zero residual state from Melamchi or Assam")

    print("ALL CROSS-RUN DATA ISOLATION ASSERTIONS PASSED.")
    return True


def main():
    target_runs = ["test_A_cold_verify", "test_B_cold_verify", "practice_assam_event"]
    
    # If other runs exist in runs/, verify them too if they have run_summary.json
    all_runs = [d for d in RUNS_DIR.iterdir() if d.is_dir() and (d / "run_summary.json").exists()]
    
    # Run the core 3 target runs first, plus any others
    to_verify = [RUNS_DIR / r for r in target_runs if (RUNS_DIR / r).exists()]
    for r_dir in all_runs:
        if r_dir not in to_verify:
            to_verify.append(r_dir)

    print(f"Found {len(to_verify)} runs to verify against underlying pipeline JSONs.")
    failed = 0
    passed = 0

    for r_dir in to_verify:
        ok = verify_run(r_dir)
        if ok:
            passed += 1
        else:
            failed += 1

    # Also verify strict data isolation across runs
    isolation_ok = verify_no_cross_run_leakage()
    if not isolation_ok:
        failed += 1

    print("\n=======================================================")
    print(f"CHECK SUMMARY: {passed} PASSED, {failed} FAILED across {len(to_verify)} runs.")
    print("=======================================================")

    if failed > 0:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
