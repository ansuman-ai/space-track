"""
Inspect Kuro Siwo dataset from Hugging Face or local directory.
Run on your machine:
    python3 inspect_kurosiwo.py [--local-dir path/to/kurosiwo]
"""

import sys
import os
import json
import argparse
from pathlib import Path
import requests

HF_API_URL = "https://huggingface.co/api/datasets/Orion-AI-Lab/KuroSiwo"
HF_TREE_URL = "https://huggingface.co/api/datasets/Orion-AI-Lab/KuroSiwo/tree/main"


def inspect_remote():
    print("=" * 60)
    print("QUERYING HUGGING FACE FOR ORION-AI-LAB/KUROSIWO METADATA")
    print("=" * 60)

    try:
        resp = requests.get(HF_API_URL, timeout=15)
        if resp.status_code != 200:
            print(f"Failed to query HF API (HTTP {resp.status_code}): {resp.text[:200]}")
            return
        meta = resp.json()
    except Exception as e:
        print(f"Network error querying Hugging Face: {e}")
        return

    print(f"Dataset ID: {meta.get('id')}")
    print(f"Author / Org: {meta.get('author')}")
    print(f"Last Modified: {meta.get('lastModified')}")
    tags = meta.get("tags", [])
    print(f"Tags: {tags}")

    # Fetch file tree
    try:
        tree_resp = requests.get(HF_TREE_URL, timeout=20)
        if tree_resp.status_code == 200:
            files = tree_resp.json()
            total_size_bytes = sum(f.get("size", 0) for f in files if isinstance(f, dict))
            print(f"\nFiles count at root: {len(files)}")
            print(f"Total size of root items: {total_size_bytes / (1024**3):.2f} GB")
            print("Top-level files/directories:")
            for item in files[:20]:
                print(f"  - {item.get('path')} ({item.get('type')}, {item.get('size', 0) / (1024**2):.1f} MB)")
            if len(files) > 20:
                print(f"  ... and {len(files) - 20} more items.")
    except Exception as e:
        print(f"Could not fetch full tree: {e}")

    print("\nDocumented Dataset Specifications (from NeurIPS 2024 Benchmark):")
    print("  - Events: 43 global flood events across 6 continents")
    print("  - Modality: Sentinel-1 SAR (Pre/Post VV + VH) + Copernicus DEM")
    print("  - Semantic Classes: 0: Background, 1: Permanent Water, 2: Flooded Water")
    print("  - Notice: No debris class in annotations (debris handled in L2)")


def inspect_local(local_dir: str):
    print("=" * 60)
    print(f"INSPECTING LOCAL KURO SIWO DIRECTORY: {local_dir}")
    print("=" * 60)

    p = Path(local_dir)
    if not p.exists():
        print(f"Directory {local_dir} does not exist.")
        return

    # Check for event folders or subdirectories
    subdirs = [d for d in p.iterdir() if d.is_dir()]
    print(f"Found {len(subdirs)} event/sub-directories:")
    for d in subdirs[:15]:
        print(f"  - {d.name}")
    if len(subdirs) > 15:
        print(f"  ... and {len(subdirs) - 15} more directories.")

    # Inspect a sample tif or npz
    sample_files = list(p.rglob("*.tif")) + list(p.rglob("*.npy")) + list(p.rglob("*.npz"))
    print(f"\nTotal data array files found: {len(sample_files)}")
    if sample_files:
        sample = sample_files[0]
        print(f"Sample file: {sample.name}")
        if sample.suffix == ".tif":
            import rasterio
            with rasterio.open(sample) as src:
                print(f"  Shape: {src.shape}")
                print(f"  Bands count: {src.count}")
                print(f"  CRS: {src.crs}")
                print(f"  Dtype: {src.dtypes[0]}")
        elif sample.suffix in [".npy", ".npz"]:
            import numpy as np
            arr = np.load(sample)
            if hasattr(arr, "shape"):
                print(f"  Shape: {arr.shape}, Dtype: {arr.dtype}")


def main():
    parser = argparse.ArgumentParser(description="Inspect Kuro Siwo dataset")
    parser.add_argument("--local-dir", type=str, default="", help="Path to local Kuro Siwo directory")
    args = parser.parse_args()

    if args.local_dir:
        inspect_local(args.local_dir)
    else:
        inspect_remote()


if __name__ == "__main__":
    main()
