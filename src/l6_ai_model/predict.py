"""
Inference pipeline for Sentinel-1 Flood Segmentation using KuroSiwo pretrained SNUNet-CD.
Operates on arbitrary bounding boxes with tiled windowing.
"""

import os
import argparse
from pathlib import Path
from typing import Optional, Tuple, Union

import numpy as np
import rasterio
from rasterio.windows import Window
import torch
import torch.nn.functional as F

from src.l6_ai_model.model import load_model, SNUNet_ECAM

# Normalization constants verified from official KuroSiwo benchmark
DATA_MEAN = np.array([0.0953, 0.0264], dtype=np.float32).reshape(2, 1, 1)
DATA_STD = np.array([0.0427, 0.0215], dtype=np.float32).reshape(2, 1, 1)
SLOPE_MEAN = 2.1277
SLOPE_STD = 67.5048
CLAMP_MAX = 0.15


def db_to_linear(arr_db: np.ndarray, fill_nodata_db: float = -35.0) -> np.ndarray:
    """Convert Sentinel-1 RTC backscatter from decibels (dB) to linear intensity."""
    arr = np.nan_to_num(arr_db, nan=fill_nodata_db)
    return np.power(10.0, arr / 10.0, dtype=np.float32)


def compute_slope_riserun(dem: np.ndarray, cell_size: float = 30.0) -> np.ndarray:
    """
    Compute slope rise/run (dy/dx) from DEM, matching official KuroSiwo benchmark:
    slope = sqrt((dz/dx)^2 + (dz/dy)^2)
    """
    dem_clean = np.nan_to_num(dem, nan=0.0)
    dy, dx = np.gradient(dem_clean, cell_size)
    slope = np.nan_to_num(np.sqrt(dx**2 + dy**2), nan=0.0)
    return slope.astype(np.float32)


def preprocess_branch(
    vv_db: np.ndarray,
    vh_db: np.ndarray,
    slope_or_dem: Optional[np.ndarray] = None,
    is_dem: bool = False,
    use_slope: bool = True
) -> np.ndarray:
    """
    Convert S1 dB inputs to KuroSiwo 3-channel Siamese branch format:
      Channel 0: Linear VV clamped to [0, 0.15] and normalized (DATA_MEAN[0], DATA_STD[0])
      Channel 1: Linear VH clamped to [0, 0.15] and normalized (DATA_MEAN[1], DATA_STD[1])
      Channel 2: Slope rise/run standardized with (SLOPE_MEAN=2.1277, SLOPE_STD=67.5048)
                 (or zeros if use_slope=False)
    Returns:
      Array of shape (3, H, W)
    """
    vv_lin = np.clip(db_to_linear(vv_db, fill_nodata_db=-30.0), 0.0, CLAMP_MAX)
    vh_lin = np.clip(db_to_linear(vh_db, fill_nodata_db=-35.0), 0.0, CLAMP_MAX)
    s1 = np.stack([vv_lin, vh_lin], axis=0) # [2, H, W]
    s1_norm = (s1 - DATA_MEAN) / DATA_STD

    if use_slope and slope_or_dem is not None:
        if is_dem:
            slope = compute_slope_riserun(slope_or_dem)
        else:
            # If slope in degrees was passed (values in [0, 90]), convert to rise/run
            if np.nanmax(slope_or_dem) <= 90.0:
                slope = np.nan_to_num(np.tan(np.radians(slope_or_dem)), nan=0.0)
            else:
                slope = np.nan_to_num(slope_or_dem, nan=0.0)
        ch3 = ((slope - SLOPE_MEAN) / SLOPE_STD)[np.newaxis, :, :]
    else:
        ch3 = np.zeros((1, vv_db.shape[0], vv_db.shape[1]), dtype=np.float32)

    return np.concatenate([s1_norm, ch3], axis=0).astype(np.float32)


def predict(
    pre_vv_path: str,
    pre_vh_path: str,
    post_vv_path: str,
    post_vh_path: str,
    slope_path: Optional[str] = None,
    weights_path: str = "weights/best_segmentation.pt",
    output_dir: str = "outputs",
    use_slope: bool = True,
    tile_size: int = 224,
    stride: int = 112,
    device: str = "cpu"
) -> Tuple[str, str]:
    """
    Run tiled SNUNet inference on arbitrary bounding box GeoTIFFs.
    Produces:
      1) flood_probability.tif: Float32 [0.0, 1.0]
      2) flood_mask.tif: UInt8 (0: No water, 1: Permanent water, 2: Flooded water)
    """
    os.makedirs(output_dir, exist_ok=True)
    model = load_model(weights_path, device=device)

    with rasterio.open(pre_vv_path) as src_meta:
        meta = src_meta.meta.copy()
        height, width = src_meta.shape

    with rasterio.open(pre_vv_path) as s:
        pre_vv = s.read(1)
    with rasterio.open(pre_vh_path) as s:
        pre_vh = s.read(1)
    with rasterio.open(post_vv_path) as s:
        post_vv = s.read(1)
    with rasterio.open(post_vh_path) as s:
        post_vh = s.read(1)

    slope = None
    if slope_path and os.path.exists(slope_path):
        with rasterio.open(slope_path) as s:
            slope = s.read(1)

    xA_full = preprocess_branch(pre_vv, pre_vh, slope, use_slope=use_slope)
    xB_full = preprocess_branch(post_vv, post_vh, slope, use_slope=use_slope)

    # Accumulator buffers for smooth blending
    logit_acc = np.zeros((3, height, width), dtype=np.float32)
    weight_acc = np.zeros((height, width), dtype=np.float32)

    # 2D Hann window for blending
    hann_1d = np.hanning(tile_size)
    window_2d = np.outer(hann_1d, hann_1d).astype(np.float32)
    window_2d = np.clip(window_2d, 1e-4, 1.0)

    y_steps = list(range(0, max(1, height - tile_size + 1), stride))
    if height > tile_size and y_steps[-1] != height - tile_size:
        y_steps.append(height - tile_size)
    x_steps = list(range(0, max(1, width - tile_size + 1), stride))
    if width > tile_size and x_steps[-1] != width - tile_size:
        x_steps.append(width - tile_size)

    coords = []
    patches_A = []
    patches_B = []

    for y in y_steps:
        for x in x_steps:
            y_end = min(y + tile_size, height)
            x_end = min(x + tile_size, width)
            h_actual = y_end - y
            w_actual = x_end - x

            patch_xA = np.zeros((3, tile_size, tile_size), dtype=np.float32)
            patch_xB = np.zeros((3, tile_size, tile_size), dtype=np.float32)
            patch_xA[:, :h_actual, :w_actual] = xA_full[:, y:y_end, x:x_end]
            patch_xB[:, :h_actual, :w_actual] = xB_full[:, y:y_end, x:x_end]

            coords.append((y, x, y_end, x_end, h_actual, w_actual))
            patches_A.append(patch_xA)
            patches_B.append(patch_xB)

    batch_size = 16
    num_patches = len(coords)
    for b in range(0, num_patches, batch_size):
        b_end = min(b + batch_size, num_patches)
        b_xA = torch.from_numpy(np.stack(patches_A[b:b_end])).to(device)
        b_xB = torch.from_numpy(np.stack(patches_B[b:b_end])).to(device)

        with torch.no_grad():
            b_logits = model(b_xA, b_xB).cpu().numpy()

        for i, idx in enumerate(range(b, b_end)):
            y, x, y_end, x_end, h_actual, w_actual = coords[idx]
            w = window_2d[:h_actual, :w_actual]
            logit_acc[:, y:y_end, x:x_end] += b_logits[i, :, :h_actual, :w_actual] * w
            weight_acc[y:y_end, x:x_end] += w

    valid_mask = weight_acc > 0
    logit_acc[:, valid_mask] /= weight_acc[valid_mask]

    # Softmax probabilities and argmax mask
    t_logits = torch.from_numpy(logit_acc).unsqueeze(0)
    probs = F.softmax(t_logits, dim=1).squeeze(0).numpy()
    pred_mask = np.argmax(logit_acc, axis=0).astype(np.uint8)
    flood_prob = probs[2].astype(np.float32)

    # Save flood probability GeoTIFF
    prob_path = os.path.join(output_dir, "flood_probability.tif")
    meta_prob = meta.copy()
    meta_prob.update({"count": 1, "dtype": "float32", "nodata": None})
    with rasterio.open(prob_path, "w", **meta_prob) as dst:
        dst.write(flood_prob, 1)

    # Save flood mask GeoTIFF
    mask_path = os.path.join(output_dir, "flood_mask.tif")
    meta_mask = meta.copy()
    meta_mask.update({"count": 1, "dtype": "uint8", "nodata": 0})
    with rasterio.open(mask_path, "w", **meta_mask) as dst:
        dst.write(pred_mask, 1)

    return prob_path, mask_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SNUNet-CD Flood Inference")
    parser.add_argument("--pre-vv", required=True)
    parser.add_argument("--pre-vh", required=True)
    parser.add_argument("--post-vv", required=True)
    parser.add_argument("--post-vh", required=True)
    parser.add_argument("--slope", default=None)
    parser.add_argument("--weights", default="weights/best_segmentation.pt")
    parser.add_argument("--out-dir", default="outputs")
    parser.add_argument("--no-slope", action="store_true")
    args = parser.parse_args()

    predict(
        args.pre_vv,
        args.pre_vh,
        args.post_vv,
        args.post_vh,
        slope_path=args.slope,
        weights_path=args.weights,
        output_dir=args.out_dir,
        use_slope=not args.no_slope
    )
