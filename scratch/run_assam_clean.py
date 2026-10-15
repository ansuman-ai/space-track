import sys
import os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Clean proxy
for _k in ["http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY"]:
    os.environ.pop(_k, None)

import time
import json
from main import run_pipeline

p_assam = Path("runs/practice_assam_event")
print("Running complete pipeline for practice_assam_event...")
t0 = time.time()
res = run_pipeline(
    bbox=[92.85, 26.55, 93.1, 26.75],
    event_date="2024-07-02",
    out_dir=str(p_assam),
    config_path="configs/default.yaml",
    no_cache=False,
    no_quicklooks=False,
)
print(f"Finished practice_assam_event in {time.time() - t0:.1f}s")
print("Status:", res.get("status"))
print("Metrics:", json.dumps(res.get("metrics"), indent=2))
