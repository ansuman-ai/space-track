import json
from pathlib import Path
from collections import Counter

old = json.load(open("runs/old_4_runs_metrics.json"))
runs = ["practice_sikkim_event", "practice_sikkim_noevent", "practice_assam_event", "practice_assam_noevent"]

new_metrics = {}
for r in runs:
    p = Path("runs") / r
    l2 = json.load(open(p / "processed/l2_stats.json"))
    obs_km2 = l2.get("areas_km2", {}).get("event_total_affected", 0)

    bld_file = p / "processed/buildings_graded.geojson"
    bld_counts = Counter()
    if bld_file.exists():
        gj = json.load(open(bld_file))
        for f in gj["features"]:
            bld_counts[f["properties"].get("damage_grade", "Unknown")] += 1

    brg_file = p / "processed/bridges_graded.geojson"
    brg_counts = Counter()
    if brg_file.exists():
        gj = json.load(open(brg_file))
        for f in gj["features"]:
            brg_counts[f["properties"].get("damage_grade", "Unknown")] += 1

    cutoff_file = p / "processed/routing/cutoff_summary.json"
    veh_cut_opt = 0
    veh_cut_pess = 0
    walk_cut_opt = 0
    walk_cut_pess = 0
    if cutoff_file.exists():
        co = json.load(open(cutoff_file))
        if "vehicle" in co:
            veh_cut_opt = co["vehicle"].get("optimistic", {}).get("cut_off_count", 0)
            veh_cut_pess = co["vehicle"].get("pessimistic", {}).get("cut_off_count", 0)
        if "walking" in co:
            walk_cut_opt = co["walking"].get("optimistic", {}).get("cut_off_count", 0)
            walk_cut_pess = co["walking"].get("pessimistic", {}).get("cut_off_count", 0)

    settle_file = p / "processed/routing/settlements.geojson"
    no_ground_opt = 0
    no_ground_pess = 0
    if settle_file.exists():
        gj = json.load(open(settle_file))
        for f in gj["features"]:
            props = f["properties"]
            v_opt = props.get("vehicle_status_opt") == "cut_off"
            w_opt = props.get("walking_status_opt") == "cut_off"
            if v_opt and w_opt:
                no_ground_opt += 1
            v_pess = props.get("vehicle_status_pess") == "cut_off"
            w_pess = props.get("walking_status_pess") == "cut_off"
            if v_pess and w_pess:
                no_ground_pess += 1

    pkg_file = p / "processed/routing/repair_packages.json"
    top_pkg = {"settlements": 0, "buildings": 0, "elements": 0}
    if pkg_file.exists():
        pkgs = json.load(open(pkg_file))
        ranked = pkgs.get("ranked_packages", [])
        if ranked:
            top_pkg = {
                "settlements": ranked[0].get("settlements_count", 0),
                "buildings": ranked[0].get("buildings_count", 0),
                "elements": ranked[0].get("element_count", 0)
            }

    new_metrics[r] = {
        "observed_km2": round(obs_km2, 4),
        "buildings": dict(bld_counts),
        "bridges": dict(brg_counts),
        "cutoff_vehicle_opt": veh_cut_opt,
        "cutoff_vehicle_pess": veh_cut_pess,
        "cutoff_walking_opt": walk_cut_opt,
        "cutoff_walking_pess": walk_cut_pess,
        "no_ground_access_opt": no_ground_opt,
        "no_ground_access_pess": no_ground_pess,
        "top_repair_package": top_pkg
    }

with open("runs/new_4_runs_metrics.json", "w") as f:
    json.dump(new_metrics, f, indent=2)

print("\n=== COMPARISON OLD VS NEW ===")
for r in runs:
    o = old[r]
    n = new_metrics[r]
    print(f"\n========================================================")
    print(f"RUN: {r}")
    print(f"========================================================")
    print(f"Observed area:       old {o['observed_km2']} km² -> new {n['observed_km2']} km²")
    print(f"Buildings:           old {o['buildings']} -> new {n['buildings']}")
    print(f"Bridges:             old {o['bridges']} -> new {n['bridges']}")
    print(f"Cutoff Vehicle:      old {o['cutoff_vehicle']} -> new opt={n['cutoff_vehicle_opt']}, pess={n['cutoff_vehicle_pess']}")
    print(f"Cutoff Walking:      old {o['cutoff_walking']} -> new opt={n['cutoff_walking_opt']}, pess={n['cutoff_walking_pess']}")
    print(f"No ground access:    old {o['no_ground_access']} -> new opt={n['no_ground_access_opt']}, pess={n['no_ground_access_pess']}")
    print(f"Top repair package:  old {o['top_repair_package']} -> new {n['top_repair_package']}")
