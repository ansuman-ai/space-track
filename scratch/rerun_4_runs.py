import os
import sys
import json
import shutil
import time
from pathlib import Path

# Clean proxy
for _k in ["http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY"]:
    os.environ.pop(_k, None)

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from main import run_pipeline

archive_dir = ROOT_DIR / "runs" / "_archive"
archive_dir.mkdir(parents=True, exist_ok=True)

runs_to_process = [
    {
        "name": "practice_sikkim_event",
        "bbox": [88.58, 27.53, 88.72, 27.67],
        "event_date": "2023-10-04",
    },
    {
        "name": "practice_sikkim_noevent",
        "bbox": [88.58, 27.53, 88.72, 27.67],
        "event_date": "2023-04-15",
    },
    {
        "name": "practice_assam_event",
        "bbox": [92.85, 26.55, 93.1, 26.75],
        "event_date": "2024-07-02",
    },
    {
        "name": "practice_assam_noevent",
        "bbox": [92.85, 26.55, 93.1, 26.75],
        "event_date": "2024-01-15",
    },
]

print("Starting pipeline re-runs on current master...")

for item in runs_to_process:
    r_name = item["name"]
    orig_path = ROOT_DIR / "runs" / r_name
    arch_path = archive_dir / f"{r_name}_e2e_final3"
    
    # 1. Archive old run
    if orig_path.exists():
        if arch_path.exists():
            shutil.rmtree(arch_path)
        print(f"Archiving {r_name} -> {arch_path.name}")
        shutil.copytree(orig_path, arch_path)
        
        # Keep raw and s2_cache, remove all processed outputs
        raw_backup = ROOT_DIR / "runs" / f"_{r_name}_raw_tmp"
        if raw_backup.exists(): shutil.rmtree(raw_backup)
        if (orig_path / "raw").exists():
            shutil.copytree(orig_path / "raw", raw_backup / "raw")
        if (orig_path / "interim" / "s2_cache").exists():
            shutil.copytree(orig_path / "interim" / "s2_cache", raw_backup / "interim" / "s2_cache")
        if (orig_path / "control" / "raw").exists():
            shutil.copytree(orig_path / "control" / "raw", raw_backup / "control" / "raw")
        if (orig_path / "control" / "interim" / "s2_cache").exists():
            shutil.copytree(orig_path / "control" / "interim" / "s2_cache", raw_backup / "control" / "interim" / "s2_cache")
        if (orig_path / "event_name.txt").exists():
            raw_backup.mkdir(parents=True, exist_ok=True)
            shutil.copy2(orig_path / "event_name.txt", raw_backup / "event_name.txt")

        shutil.rmtree(orig_path)
        orig_path.mkdir(parents=True, exist_ok=True)
        
        if (raw_backup / "raw").exists():
            shutil.copytree(raw_backup / "raw", orig_path / "raw")
        if (raw_backup / "interim" / "s2_cache").exists():
            shutil.copytree(raw_backup / "interim" / "s2_cache", orig_path / "interim" / "s2_cache")
        if (raw_backup / "control" / "raw").exists():
            shutil.copytree(raw_backup / "control" / "raw", orig_path / "control" / "raw")
        if (raw_backup / "control" / "interim" / "s2_cache").exists():
            shutil.copytree(raw_backup / "control" / "interim" / "s2_cache", orig_path / "control" / "interim" / "s2_cache")
        if (raw_backup / "event_name.txt").exists():
            shutil.copy2(raw_backup / "event_name.txt", orig_path / "event_name.txt")
        shutil.rmtree(raw_backup)
    else:
        orig_path.mkdir(parents=True, exist_ok=True)

    print(f"\n==================================================================")
    print(f"RUNNING: {r_name}")
    print(f"Bbox: {item['bbox']} | Date: {item['event_date']}")
    print(f"==================================================================")
    
    t0 = time.time()
    run_pipeline(
        bbox=item["bbox"],
        event_date=item["event_date"],
        out_dir=str(orig_path),
        config_path="configs/default.yaml",
        no_cache=False,
        no_quicklooks=False,
    )
    print(f"FINISHED {r_name} in {time.time() - t0:.1f}s\n")

print("All 4 runs finished successfully!")
