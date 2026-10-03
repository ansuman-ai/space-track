"""
Kuro Siwo PyTorch Dataset loader.
Constructs 6-channel tensors: [pre_vv, pre_vh, post_vv, post_vh, log_ratio, dem_slope]
Splits strictly by event ID.
"""

import os
import random
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
import numpy as np
import torch
from torch.utils.data import Dataset
import rasterio


def compute_slope(dem: np.ndarray, cell_size: float = 30.0) -> np.ndarray:
    """Compute terrain slope in degrees using 2D finite-difference gradient."""
    dy, dx = np.gradient(dem, cell_size)
    slope_rad = np.arctan(np.sqrt(dx**2 + dy**2))
    return np.degrees(slope_rad).astype(np.float32)


def to_db(linear: np.ndarray, eps: float = 1e-5) -> np.ndarray:
    """Convert linear SAR intensity to decibels (dB), normalized to [-30, 0] -> [0, 1]."""
    db = 10.0 * np.log10(np.clip(linear, eps, 1.0))
    # Normalize approx -30 dB to 0 dB into [0, 1]
    norm = np.clip((db + 30.0) / 30.0, 0.0, 1.0)
    return norm.astype(np.float32)


class KuroSiwoDataset(Dataset):
    """
    Dataset loader for Kuro Siwo multi-temporal SAR and DEM patches.
    Input channels (6):
      0: pre VV (dB normalized)
      1: pre VH (dB normalized)
      2: post VV (dB normalized)
      3: post VH (dB normalized)
      4: log-ratio (post_vv / pre_vv)
      5: DEM slope (normalized 0 to 60 deg -> [0, 1])
    """

    def __init__(
        self,
        root_dir: str,
        event_ids: List[str],
        patch_size: int = 256,
        is_training: bool = False,
        transform: bool = True
    ):
        self.root_dir = Path(root_dir)
        self.event_ids = event_ids
        self.patch_size = patch_size
        self.is_training = is_training
        self.transform = transform

        self.samples = []
        self._index_samples()

    def _index_samples(self):
        """Index all patch or tile files belonging strictly to the assigned event IDs."""
        for event_id in self.event_ids:
            event_path = self.root_dir / event_id
            if not event_path.exists():
                # Allow flat files prefixed with event_id
                matched_files = list(self.root_dir.glob(f"*{event_id}*"))
                if not matched_files:
                    continue
                for f in matched_files:
                    if f.suffix in [".tif", ".npz", ".npy"] and "mask" not in f.name:
                        self.samples.append({
                            "event_id": event_id,
                            "data_path": f,
                            "type": "flat"
                        })
            else:
                # Subdirectory containing patches or scenes
                patches = list(event_path.rglob("*.tif")) + list(event_path.rglob("*.npz"))
                for p in patches:
                    if "label" not in p.name and "mask" not in p.name:
                        self.samples.append({
                            "event_id": event_id,
                            "data_path": p,
                            "type": "dir"
                        })

    def __len__(self) -> int:
        return len(self.samples)

    def _load_data_and_mask(self, sample_info: Dict[str, Any]) -> Tuple[np.ndarray, np.ndarray]:
        """Load 6 channels and ground-truth mask."""
        path = sample_info["data_path"]

        if path.suffix == ".npz":
            data = np.load(path)
            pre_vv = data["pre_vv"]
            pre_vh = data["pre_vh"]
            post_vv = data["post_vv"]
            post_vh = data["post_vh"]
            dem = data.get("dem", np.zeros_like(post_vv))
            mask = data.get("mask", np.zeros_like(post_vv, dtype=np.uint8))
        elif path.suffix == ".tif":
            with rasterio.open(path) as src:
                arr = src.read()
                # Expect bands: [pre_vv, pre_vh, post_vv, post_vh, dem]
                if arr.shape[0] >= 4:
                    pre_vv = arr[0]
                    pre_vh = arr[1]
                    post_vv = arr[2]
                    post_vh = arr[3]
                    dem = arr[4] if arr.shape[0] >= 5 else np.zeros_like(post_vv)
                else:
                    pre_vv = arr[0]
                    pre_vh = arr[0] * 0.2
                    post_vv = arr[0]
                    post_vh = arr[0] * 0.2
                    dem = np.zeros_like(post_vv)

            # Try locating companion mask file
            mask_path = path.parent / f"{path.stem}_mask{path.suffix}"
            if not mask_path.exists():
                mask_path = path.parent / f"{path.stem}_label{path.suffix}"

            if mask_path.exists():
                with rasterio.open(mask_path) as m_src:
                    mask = m_src.read(1)
            else:
                mask = np.zeros_like(post_vv, dtype=np.uint8)
        else:
            raise ValueError(f"Unsupported file format: {path}")

        # Compute derived channels
        pre_vv_db = to_db(pre_vv)
        pre_vh_db = to_db(pre_vh)
        post_vv_db = to_db(post_vv)
        post_vh_db = to_db(post_vh)

        # Log ratio: post / pre (dB difference = post_db - pre_db)
        log_ratio = np.clip((post_vv_db - pre_vv_db + 1.0) / 2.0, 0.0, 1.0).astype(np.float32)

        # DEM slope
        slope_deg = compute_slope(dem)
        norm_slope = np.clip(slope_deg / 60.0, 0.0, 1.0).astype(np.float32)

        # Binary flood target: Kuro Siwo class 2 is flooded water
        # If mask contains {0, 1, 2}, map 2 -> 1, others -> 0
        if mask.max() > 1:
            target_mask = (mask == 2).astype(np.float32)
        else:
            target_mask = (mask > 0).astype(np.float32)

        # Stack to 6-channel array: (6, H, W)
        channels = np.stack([
            pre_vv_db, pre_vh_db, post_vv_db, post_vh_db, log_ratio, norm_slope
        ], axis=0)

        return channels, target_mask

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor, str]:
        sample_info = self.samples[idx]
        channels, mask = self._load_data_and_mask(sample_info)

        # Data augmentation during training
        if self.is_training and self.transform:
            # Random horizontal flip
            if random.random() > 0.5:
                channels = np.flip(channels, axis=2).copy()
                mask = np.flip(mask, axis=1).copy()
            # Random vertical flip
            if random.random() > 0.5:
                channels = np.flip(channels, axis=1).copy()
                mask = np.flip(mask, axis=0).copy()

        tensor_x = torch.from_numpy(channels).float()
        tensor_y = torch.from_numpy(mask).float().unsqueeze(0)

        return tensor_x, tensor_y, sample_info["event_id"]
