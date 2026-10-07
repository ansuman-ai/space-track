import sys, os, time
from pathlib import Path
import numpy as np
import rasterio
from rasterio.features import rasterize
import geopandas as gpd
from shapely.geometry import box
import torch
import torch.nn.functional as F
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

sys.path.insert(0, '/home/zeus/Downloads/project1')
from src.l2_detection.flat_floodplain import detect_flat_floodplain_hazard, otsu_threshold

# Add path for project1-l6
sys.path.insert(0, '/home/zeus/Downloads/project1-l6')
from src.l6_ai_model.model import load_model
from src.l6_ai_model.predict import predict

def evaluate_run(run_dir, aoi_shp, event_shp, is_event=True, device='cpu', weights_path=None):
    interim = Path(run_dir) / 'interim'
    with rasterio.open(interim / 'post_vv.tif') as src:
        post_vv = src.read(1)
        meta = src.meta.copy()
        transform = src.transform
        crs = src.crs
    with rasterio.open(interim / 'pre_vv.tif') as src:
        pre_vv = src.read(1)
    with rasterio.open(interim / 'post_vh.tif') as src:
        post_vh = src.read(1)
    with rasterio.open(interim / 'pre_vh.tif') as src:
        pre_vh = src.read(1)
    with rasterio.open(interim / 'slope.tif') as src:
        slope = src.read(1)
    with rasterio.open(interim / 'hand.tif') as src:
        hand = src.read(1)

    # Control post VV if available
    ctrl_post_vv = None
    ctrl_interim = Path(run_dir) / 'control' / 'interim' / 'post_vv.tif'
    if ctrl_interim.exists():
        with rasterio.open(ctrl_interim) as src:
            ctrl_post_vv = src.read(1)

    h, w = post_vv.shape

    perm_water_mask = np.zeros((h, w), dtype=np.uint8)

    # 1. Threshold detector
    aff_thresh, _, _ = detect_flat_floodplain_hazard(
        post_vv=post_vv,
        pre_vv=pre_vv,
        hand=hand,
        perm_water_mask=perm_water_mask,
        ctrl_post_vv=ctrl_post_vv,
        max_hand_m=15.0,
        min_blob_pixels=100
    )
    thresh_mask = (aff_thresh == 1)

    # 2. Kuro Siwo SNUNet
    snunet_mask = np.zeros((h, w), dtype=bool)
    if weights_path is not None:
        snunet_out_dir = Path(run_dir) / 'snunet_output'
        snunet_mask_path = snunet_out_dir / 'flood_mask.tif'
        if not snunet_mask_path.exists():
            predict(
                pre_vv_path=str(interim / 'pre_vv.tif'),
                pre_vh_path=str(interim / 'pre_vh.tif'),
                post_vv_path=str(interim / 'post_vv.tif'),
                post_vh_path=str(interim / 'post_vh.tif'),
                slope_path=str(interim / 'slope.tif'),
                weights_path=weights_path,
                output_dir=str(snunet_out_dir),
                device=device
            )
        with rasterio.open(snunet_mask_path) as src_s:
            s_arr = src_s.read(1)
            # class 2 = flood water in KuroSiwo
            snunet_mask = (s_arr == 2) & (hand <= 15.0)

    # 3. Read EMS AOI and Ground truth
    aoi_gdf = gpd.read_file(aoi_shp).to_crs(crs)
    aoi_mask = rasterize(
        [(geom, 1) for geom in aoi_gdf.geometry if geom is not None and not geom.is_empty],
        out_shape=(h, w),
        transform=transform,
        fill=0,
        default_value=1,
        dtype=np.uint8
    ) == 1

    gt_mask = np.zeros((h, w), dtype=bool)
    if is_event and Path(event_shp).exists():
        ev_gdf = gpd.read_file(event_shp).to_crs(crs)
        gt_mask = rasterize(
            [(geom, 1) for geom in ev_gdf.geometry if geom is not None and not geom.is_empty],
            out_shape=(h, w),
            transform=transform,
            fill=0,
            default_value=1,
            dtype=np.uint8
        ) == 1
        gt_mask = gt_mask & aoi_mask

    # Calculate metrics inside AOI
    def calc_metrics(pred_mask, gt_m, valid_aoi):
        p = pred_mask & valid_aoi
        g = gt_m & valid_aoi
        tp = np.sum(p & g)
        fp = np.sum(p & (~g))
        fn = np.sum((~p) & g)
        tn = np.sum((~p) & (~g))

        area_km2 = np.sum(p) * 0.0001
        iou = tp / max(1, (tp + fp + fn))
        p_val = tp / max(1, (tp + fp))
        r_val = tp / max(1, (tp + fn))
        f1 = 2 * p_val * r_val / max(1e-6, (p_val + r_val))
        return {
            'area_km2': round(float(area_km2), 4),
            'iou': round(float(iou), 4),
            'f1': round(float(f1), 4),
            'precision': round(float(p_val), 4),
            'recall': round(float(r_val), 4)
        }

    m_thresh = calc_metrics(thresh_mask, gt_mask, aoi_mask)
    m_snunet = calc_metrics(snunet_mask, gt_mask, aoi_mask)

    # Combined detector (ensemble: union or intersection)
    ensemble_mask = thresh_mask | snunet_mask
    m_ensemble = calc_metrics(ensemble_mask, gt_mask, aoi_mask)

    return {
        'threshold': m_thresh,
        'snunet': m_snunet,
        'ensemble': m_ensemble,
        'aoi_mask': aoi_mask,
        'gt_mask': gt_mask,
        'thresh_mask': thresh_mask,
        'snunet_mask': snunet_mask,
        'post_vv': post_vv,
        'transform': transform,
        'crs': crs
    }

if __name__ == '__main__':
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print('Using device:', device)
    weights_path = '/home/zeus/Downloads/project1-l6/weights/best_segmentation.pt'

    # 1. EMSR659 Italy
    aoi_659 = 'validation/emsr659/EMSR659_AOI02_DEL_PRODUCT_v2/EMSR659_AOI02_DEL_PRODUCT_v2/EMSR659_AOI02_DEL_PRODUCT_areaOfInterestA_v2.shp'
    ev_659 = 'validation/emsr659/EMSR659_AOI02_DEL_PRODUCT_v2/EMSR659_AOI02_DEL_PRODUCT_v2/EMSR659_AOI02_DEL_PRODUCT_observedEventA_v2.shp'

    print('Evaluating EMSR659 Event (Italy)...')
    res_659_ev = evaluate_run('runs/emsr659_val', aoi_659, ev_659, is_event=True, device=device, weights_path=weights_path)
    print('Evaluating EMSR659 No-Event (Italy)...')
    res_659_noev = evaluate_run('runs/emsr659_noevent', aoi_659, ev_659, is_event=False, device=device, weights_path=weights_path)

    # 2. EMSR692 Greece
    aoi_692 = 'validation/emsr692/EMSR692_AOI02_DEL_PRODUCT_areaOfInterestA_v2.shp'
    ev_692 = 'validation/emsr692/EMSR692_AOI02_DEL_PRODUCT_observedEventA_v2.shp'

    print('Evaluating EMSR692 Event (Greece)...')
    res_692_ev = evaluate_run('runs/emsr692_val', aoi_692, ev_692, is_event=True, device=device, weights_path=weights_path)
    print('Evaluating EMSR692 No-Event (Greece)...')
    res_692_noev = evaluate_run('runs/emsr692_noevent', aoi_692, ev_692, is_event=False, device=device, weights_path=weights_path)

    print('\n================ RESULTS SUMMARY ================')
    print('EMSR659 (Italy) Event:')
    print('  Threshold Detector: ', res_659_ev['threshold'])
    print('  Kuro Siwo SNUNet:   ', res_659_ev['snunet'])
    print('  Ensemble (Union):   ', res_659_ev['ensemble'])
    print('EMSR659 (Italy) No-Event:')
    print('  Threshold Detector Area km2: ', res_659_noev['threshold']['area_km2'])
    print('  Kuro Siwo SNUNet Area km2:   ', res_659_noev['snunet']['area_km2'])

    print('\nEMSR692 (Greece) Event:')
    print('  Threshold Detector: ', res_692_ev['threshold'])
    print('  Kuro Siwo SNUNet:   ', res_692_ev['snunet'])
    print('  Ensemble (Union):   ', res_692_ev['ensemble'])
    print('EMSR692 (Greece) No-Event:')
    print('  Threshold Detector Area km2: ', res_692_noev['threshold']['area_km2'])
    print('  Kuro Siwo SNUNet Area km2:   ', res_692_noev['snunet']['area_km2'])
