"""
Flat-floodplain terrain classification and inundation detection module.
Operates on broad low-gradient floodplains where channel-confined hydraulic
assumptions and strict stream-proximity pruning do not apply.
"""

from typing import Dict, Any, Tuple, Optional
import numpy as np
import logging
from scipy.ndimage import label

logger = logging.getLogger("flat_floodplain")


def otsu_threshold(data: np.ndarray, nbins: int = 256) -> float:
    """Computes Otsu's optimal threshold on 1D continuous array."""
    valid = data[np.isfinite(data)]
    if len(valid) == 0:
        return -15.0
    counts, bin_edges = np.histogram(valid, bins=nbins)
    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2.0
    weight1 = np.cumsum(counts)
    weight2 = np.cumsum(counts[::-1])[::-1]
    total = np.maximum(weight1, 1)
    total_rev = np.maximum(weight2[::-1], 1)
    mean1 = np.cumsum(counts * bin_centers) / total
    mean2 = (np.cumsum((counts * bin_centers)[::-1]) / total_rev)[::-1]
    variance = weight1[:-1] * weight2[1:] * (mean1[:-1] - mean2[1:]) ** 2
    if len(variance) == 0:
        return float(np.median(valid))
    idx = int(np.argmax(variance))
    return float(bin_centers[idx])


def classify_terrain_regime(
    slope: np.ndarray,
    hand: np.ndarray,
    slope_median_threshold: float = 8.0,
    slope_low_pct_threshold: float = 40.0,
    hand_low_pct_threshold: float = 50.0
) -> Tuple[str, Dict[str, float]]:
    """
    Classifies terrain into 'flat_floodplain' vs 'steep_valley'
    based on slope and Height Above Nearest Drainage (HAND) distributions.
    
    Returns:
      (regime, stats_dict)
    """
    valid_slope = slope[np.isfinite(slope)]
    valid_hand = hand[np.isfinite(hand)]

    if len(valid_slope) == 0 or len(valid_hand) == 0:
        return "steep_valley", {}

    median_slope = float(np.median(valid_slope))
    pct_slope_lt_5 = float(np.mean(valid_slope < 5.0) * 100.0)
    median_hand = float(np.median(valid_hand))
    pct_hand_le_15 = float(np.mean(valid_hand <= 15.0) * 100.0)

    stats = {
        "median_slope": round(median_slope, 2),
        "pct_slope_lt_5": round(pct_slope_lt_5, 2),
        "median_hand": round(median_hand, 2),
        "pct_hand_le_15": round(pct_hand_le_15, 2)
    }

    if (median_slope < slope_median_threshold and 
        pct_slope_lt_5 > slope_low_pct_threshold and 
        pct_hand_le_15 > hand_low_pct_threshold):
        regime = "flat_floodplain"
    else:
        regime = "steep_valley"

    return regime, stats


def detect_flat_floodplain_hazard(
    post_vv: np.ndarray,
    pre_vv: np.ndarray,
    hand: np.ndarray,
    perm_water_mask: np.ndarray,
    post_vh: Optional[np.ndarray] = None,
    pre_vh: Optional[np.ndarray] = None,
    ctrl_post_vv: Optional[np.ndarray] = None,
    ctrl_pre_vv: Optional[np.ndarray] = None,
    seasonal_post_vv: Optional[np.ndarray] = None,
    s2_event_valid: Optional[np.ndarray] = None,
    s2_data: Optional[Dict[str, Any]] = None,
    nodata_mask: Optional[np.ndarray] = None,
    max_hand_m: float = 15.0,
    min_blob_pixels: int = 100,
    combine_mode: str = "union"
) -> Tuple[np.ndarray, np.ndarray, Dict[str, Any]]:
    """
    Detects open-water and inundated floodplain hazard on flat terrain without stream-proximity pruning.
    
    Criteria:
      1. S1 SAR change & low backscatter:
         - Post VV low (specular water threshold from Otsu on floodplain, bounded [-17, -13.5])
         - Significant attenuation vs Pre VV (calibrated from control pair / physical floor)
         - If VH available, consistent polarimetric change
         - Constrained to floodplain HAND (<= max_hand_m)
         - Permanent baseline water subtracted
         - Rejection of persistent seasonal water (e.g. paddies)
      2. S2 Optical water expansion when clear:
         - Delta MNDWI > 0.10 OR Delta NDWI > 0.12 OR (turbid flood water with Post MNDWI > -0.05 & Delta NIR < -0.10)
         - Pre-event permanent and seasonal water subtracted
      3. Integration:
         - S2 where clear and S1 where cloudy, or Union across sensors
      4. Morphological blob filtering:
         - Connected components >= min_blob_pixels to reject residual radar speckle
          
    Returns:
      (aff_clean, source_mask, thresholds_dict)
    """
    h, w = post_vv.shape
    if nodata_mask is None:
        nodata_mask = np.zeros((h, w), dtype=np.uint8)
    if s2_event_valid is None:
        s2_event_valid = np.zeros((h, w), dtype=bool)

    # Convert to dB if in linear scale
    post_db = post_vv if np.nanmin(post_vv) < 0.0 else 10.0 * np.log10(np.maximum(post_vv, 1e-5))
    pre_db = pre_vv if np.nanmin(pre_vv) < 0.0 else 10.0 * np.log10(np.maximum(pre_vv, 1e-5))

    fp_mask = (hand <= max_hand_m) & (nodata_mask == 0) & (perm_water_mask == 0) & np.isfinite(post_db) & np.isfinite(pre_db)

    # 1. Post VV water threshold via Otsu on floodplain
    post_fp_vals = post_db[fp_mask]
    t_otsu = otsu_threshold(post_fp_vals)
    # Physically bounded between -17.0 dB and -13.5 dB
    t_water = float(np.clip(t_otsu, -17.0, -13.5))

    # 2. Attenuation threshold (Delta VV)
    d_vv = post_db - pre_db
    if ctrl_post_vv is not None and ctrl_pre_vv is not None:
        ctrl_post_db = ctrl_post_vv if np.nanmin(ctrl_post_vv) < 0.0 else 10.0 * np.log10(np.maximum(ctrl_post_vv, 1e-5))
        ctrl_pre_db = ctrl_pre_vv if np.nanmin(ctrl_pre_vv) < 0.0 else 10.0 * np.log10(np.maximum(ctrl_pre_vv, 1e-5))
        ctrl_d_vv = ctrl_post_db - ctrl_pre_db
        ctrl_h, ctrl_w = ctrl_d_vv.shape
        c_h, c_w = min(h, ctrl_h), min(w, ctrl_w)
        ctrl_fp_vals = ctrl_d_vv[:c_h, :c_w][fp_mask[:c_h, :c_w] & np.isfinite(ctrl_d_vv[:c_h, :c_w])]
        if len(ctrl_fp_vals) >= 100:
            p1 = float(np.percentile(ctrl_fp_vals, 1.0))
            t_diff = float(np.clip(p1, -5.0, -3.5))
        else:
            t_diff = -3.8
    else:
        t_diff = -3.8

    logger.info(f"[Flat Floodplain] Calibrated thresholds: Water Post VV < {t_water:.2f} dB, Delta VV < {t_diff:.2f} dB, max HAND <= {max_hand_m} m")

    s1_cand = (post_db < t_water) & (d_vv < t_diff) & fp_mask

    # If seasonal control S1 available, reject pixels that were already low backscatter water in normal seasonal conditions
    if seasonal_post_vv is not None:
        seas_db = seasonal_post_vv if np.nanmin(seasonal_post_vv) < 0.0 else 10.0 * np.log10(np.maximum(seasonal_post_vv, 1e-5))
        s_h, s_w = min(h, seas_db.shape[0]), min(w, seas_db.shape[1])
        s1_cand[:s_h, :s_w] = s1_cand[:s_h, :s_w] & (seas_db[:s_h, :s_w] > -13.0)

    # 3. Sentinel-2 Optical detection when clear
    s2_cand = np.zeros((h, w), dtype=bool)
    if s2_data and s2_data.get('pre_composite') is not None and s2_data.get('post_composite') is not None:
        pre_comp = s2_data['pre_composite']
        post_comp = s2_data['post_composite']
        if pre_comp and post_comp and 'b03' in pre_comp and 'b11' in pre_comp and 'b03' in post_comp and 'b11' in post_comp:
            h_s2, w_s2 = post_comp['b03'].shape
            mh, mw = min(h, h_s2), min(w, w_s2)
            
            b03_post = post_comp['b03'][:mh, :mw].astype(np.float32) / 10000.0
            b08_post = post_comp['b08'][:mh, :mw].astype(np.float32) / 10000.0 if 'b08' in post_comp else np.zeros((mh, mw), dtype=np.float32)
            b11_post = post_comp['b11'][:mh, :mw].astype(np.float32) / 10000.0

            b03_pre = pre_comp['b03'][:mh, :mw].astype(np.float32) / 10000.0
            b08_pre = pre_comp['b08'][:mh, :mw].astype(np.float32) / 10000.0 if 'b08' in pre_comp else np.zeros((mh, mw), dtype=np.float32)
            b11_pre = pre_comp['b11'][:mh, :mw].astype(np.float32) / 10000.0

            mndwi_post = (b03_post - b11_post) / (b03_post + b11_post + 1e-5)
            mndwi_pre = (b03_pre - b11_pre) / (b03_pre + b11_pre + 1e-5)
            d_mndwi = mndwi_post - mndwi_pre

            ndwi_post = (b03_post - b08_post) / (b03_post + b08_post + 1e-5)
            ndwi_pre = (b03_pre - b08_pre) / (b03_pre + b08_pre + 1e-5)
            d_ndwi = ndwi_post - ndwi_pre
            d_b08 = b08_post - b08_pre

            # Permanent & seasonal baseline optical water
            perm_opt_water = (mndwi_pre > 0.0)
            if s2_data.get('ctrl_post_composite') is not None and 'b03' in s2_data['ctrl_post_composite'] and 'b11' in s2_data['ctrl_post_composite']:
                c_b03 = s2_data['ctrl_post_composite']['b03'][:mh, :mw].astype(np.float32) / 10000.0
                c_b11 = s2_data['ctrl_post_composite']['b11'][:mh, :mw].astype(np.float32) / 10000.0
                c_mndwi = (c_b03 - c_b11) / (c_b03 + c_b11 + 1e-5)
                perm_opt_water |= (c_mndwi > 0.0)

            # Sub-grid valid clear sky mask
            if s2_event_valid is not None:
                s2_val_sub = s2_event_valid[:mh, :mw]
            else:
                s2_val_sub = (b03_post > 0.0) & (b11_post > 0.0) & np.isfinite(b03_post) & np.isfinite(b11_post)
            fp_sub = fp_mask[:mh, :mw]

            opt_flood_sub = s2_val_sub & fp_sub & (~perm_opt_water) & (
                (d_mndwi > 0.10) | (d_ndwi > 0.12) | ((mndwi_post > -0.05) & (d_b08 < -0.10))
            )

            s2_cand[:mh, :mw] = opt_flood_sub

    # Combined candidate mask
    if combine_mode == "union":
        cand_total = s1_cand | s2_cand
    else:
        # S2 optical where clear, S1 SAR where cloudy
        cand_total = np.where(s2_event_valid, s2_cand, s1_cand)

    # 4. Blob size filtering (min_blob_pixels to reject speckle without stream proximity)
    lbl, num = label(cand_total)
    counts = np.bincount(lbl.ravel())
    large_blobs = np.where(counts >= min_blob_pixels)[0]
    large_blobs = large_blobs[large_blobs > 0]
    aff_clean = np.isin(lbl, large_blobs).astype(np.uint8)

    # Source mask: 1 = S2, 2 = S1
    source_mask = np.zeros((h, w), dtype=np.uint8)
    source_mask[(aff_clean == 1) & s2_event_valid] = 1
    source_mask[(aff_clean == 1) & (~s2_event_valid)] = 2

    thresholds_dict = {
        "t_water_db": t_water,
        "t_diff_db": t_diff,
        "max_hand_m": max_hand_m,
        "min_blob_pixels": min_blob_pixels,
        "combine_mode": combine_mode
    }

    return aff_clean, source_mask, thresholds_dict
