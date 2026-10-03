"""
Adaptive thresholding module for Layer 2 detection.
Computes Otsu thresholding, radiometric change limits, and physical terrain bounds.
"""

from typing import Tuple, Optional
import numpy as np
from scipy.ndimage import uniform_filter


def smooth_log_ratio_mean(arr: np.ndarray, window_size: int = 5) -> np.ndarray:
    """
    Smooth log_ratio with a uniform mean filter of size window_size x window_size.
    Handles NaNs appropriately by normalizing with non-NaN weights.
    """
    valid = np.isfinite(arr)
    arr_clean = np.where(valid, arr, 0.0)
    num = uniform_filter(arr_clean, size=window_size, mode='reflect')
    den = uniform_filter(valid.astype(np.float32), size=window_size, mode='reflect')
    smoothed = np.where(den > 0.5, num / np.maximum(den, 1e-6), np.nan)
    return smoothed.astype(np.float32)


def compute_control_percentile_threshold(
    smoothed_control_lr: np.ndarray,
    hand: np.ndarray,
    shadow_mask: np.ndarray,
    nodata_mask: Optional[np.ndarray] = None,
    max_hand_m: float = 40.0,
    false_alarm_rate_pct: float = 1.0
) -> float:
    """
    Computes threshold as the specified percentile (e.g. 1st percentile) of
    smoothed CONTROL log_ratio_vv within the active HAND corridor outside shadow/layover.
    """
    valid = (hand <= max_hand_m) & (shadow_mask == 0) & np.isfinite(smoothed_control_lr)
    if nodata_mask is not None:
        valid &= (nodata_mask == 0)

    vals = smoothed_control_lr[valid]
    if vals.size < 50:
        return -2.6

    t_val = float(np.percentile(vals, false_alarm_rate_pct))
    return t_val


def compute_s2_control_thresholds(
    d_ndvi_ctrl: np.ndarray,
    d_bsi_ctrl: np.ndarray,
    ctrl_valid: np.ndarray,
    hand: np.ndarray,
    max_hand_m: float = 40.0,
    false_alarm_rate_pct: float = 1.0
) -> Tuple[float, float]:
    """
    Computes S2 spectral change thresholds from a clear CONTROL pair inside the HAND corridor:
    - Delta NDVI: lower percentile (e.g. 1st percentile)
    - Delta BSI: upper percentile (e.g. 99th percentile)
    """
    valid = ctrl_valid & (hand <= max_hand_m) & (hand >= 0) & np.isfinite(d_ndvi_ctrl) & np.isfinite(d_bsi_ctrl)
    d_ndvi_vals = d_ndvi_ctrl[valid]
    d_bsi_vals = d_bsi_ctrl[valid]

    if d_ndvi_vals.size < 100:
        return -0.30, 0.10

    t_d_ndvi = float(np.percentile(d_ndvi_vals, false_alarm_rate_pct))
    t_d_bsi = float(np.percentile(d_bsi_vals, 100.0 - false_alarm_rate_pct))
    return t_d_ndvi, t_d_bsi


def compute_s1_zscore_control_threshold(
    z_vv_asc_ctrl: np.ndarray,
    hand: np.ndarray,
    shadow_mask: np.ndarray,
    nodata_mask: Optional[np.ndarray] = None,
    max_hand_m: float = 40.0,
    false_alarm_rate_pct: float = 1.0
) -> float:
    """
    Computes S1 z-score threshold as the lower percentile (e.g. 1st percentile)
    of control z-scores inside the HAND corridor outside shadow/nodata.
    """
    valid = (hand <= max_hand_m) & (shadow_mask == 0) & np.isfinite(z_vv_asc_ctrl)
    if nodata_mask is not None:
        valid &= (nodata_mask == 0)

    vals = z_vv_asc_ctrl[valid]
    if vals.size < 50:
        return -5.0

    t_z = float(np.percentile(vals, false_alarm_rate_pct))
    return t_z


def compute_otsu_threshold(
    values: np.ndarray,
    n_bins: int = 256,
    min_val: Optional[float] = None,
    max_val: Optional[float] = None
) -> float:
    """
    Compute Otsu threshold maximizing between-class variance on 1D array of values.
    """
    clean_vals = values[np.isfinite(values)]
    if clean_vals.size < 50:
        return -16.5

    v_min = float(np.min(clean_vals)) if min_val is None else float(min_val)
    v_max = float(np.max(clean_vals)) if max_val is None else float(max_val)

    if v_max <= v_min:
        return v_min

    counts, bin_edges = np.histogram(clean_vals, bins=n_bins, range=(v_min, v_max))
    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2.0

    total_count = np.sum(counts)
    if total_count == 0:
        return -16.5

    prob = counts / total_count
    omega = np.cumsum(prob)
    mu = np.cumsum(prob * bin_centers)
    mu_t = mu[-1]

    denom = omega * (1.0 - omega) + 1e-10
    num = (mu_t * omega - mu) ** 2
    sigma_b2 = num / denom

    sigma_b2[omega <= 0.01] = 0.0
    sigma_b2[omega >= 0.99] = 0.0

    best_idx = np.argmax(sigma_b2)
    threshold = float(bin_centers[best_idx])
    return threshold


def get_adaptive_water_threshold(
    pre_vv: np.ndarray,
    hand: np.ndarray,
    shadow_mask: np.ndarray,
    hand_corridor_m: float = 15.0,
    clamp_min: float = -20.0,
    clamp_max: float = -15.5
) -> float:
    """
    Compute adaptive water backscatter threshold from pre-event VV within the HAND corridor.
    Focuses on the water-candidate sub-distribution (<= -12.0 dB) to separate specular water
    from surrounding riparian vegetation and alluvial gravel.
    """
    valid = np.isfinite(pre_vv) & (shadow_mask == 0) & (hand <= hand_corridor_m)
    vals = pre_vv[valid]
    if vals.size < 100:
        return -16.5

    # Focus on lower radar backscatter sub-distribution to capture the specular water peak
    water_cands = vals[vals <= -12.0]
    if water_cands.size < 50:
        return -16.5

    otsu_t = compute_otsu_threshold(water_cands, n_bins=128, min_val=-25.0, max_val=-12.0)
    clamped_t = float(np.clip(otsu_t, clamp_min, clamp_max))
    return clamped_t


def get_adaptive_delta_flood_threshold(
    log_ratio_vv: np.ndarray,
    candidate_mask: np.ndarray,
    default_threshold: float = -2.8
) -> float:
    """
    Compute adaptive threshold for backscatter decrease indicating flood water.
    """
    vals = log_ratio_vv[candidate_mask & np.isfinite(log_ratio_vv)]
    if vals.size < 100:
        return float(default_threshold)

    neg_vals = vals[vals < 0.0]
    if neg_vals.size < 50:
        return float(default_threshold)

    t_otsu = compute_otsu_threshold(neg_vals, n_bins=128, min_val=-15.0, max_val=0.0)
    t_clamped = float(np.clip(t_otsu, -4.5, -2.5))
    return t_clamped


def get_adaptive_debris_threshold(
    log_ratio_vv: np.ndarray,
    log_ratio_vh: np.ndarray,
    hand: np.ndarray,
    shadow_mask: np.ndarray,
    hand_debris_m: float = 45.0,
    default_vv_rise: float = 2.8,
    default_vh_rise: float = 2.2
) -> Tuple[float, float]:
    """
    Compute adaptive backscatter surge threshold for debris/gravel roughness.
    """
    valid = (hand <= hand_debris_m) & (shadow_mask == 0) & np.isfinite(log_ratio_vv)
    vv_vals = log_ratio_vv[valid]
    vh_vals = log_ratio_vh[valid]

    if vv_vals.size < 200:
        return default_vv_rise, default_vh_rise

    med_vv = float(np.median(vv_vals))
    mad_vv = float(np.median(np.abs(vv_vals - med_vv)))
    t_vv = med_vv + 2.5 * max(mad_vv, 0.8)
    t_vv = float(np.clip(t_vv, 2.5, 3.8))

    med_vh = float(np.median(vh_vals))
    mad_vh = float(np.median(np.abs(vh_vals - med_vh)))
    t_vh = med_vh + 2.2 * max(mad_vh, 0.7)
    t_vh = float(np.clip(t_vh, 2.0, 3.2))

    return t_vv, t_vh
