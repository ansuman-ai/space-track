import sys
import numpy as np
import rasterio
import rasterio.features
import geopandas as gpd

raster_path, ems_event_path, ems_aoi_path = sys.argv[1], sys.argv[2], sys.argv[3]

with rasterio.open(raster_path) as src:
    r = src.read(1)
    trans, crs, shape = src.transform, src.crs, r.shape

aoi_gdf = gpd.read_file(ems_aoi_path).to_crs(crs)
event_gdf = gpd.read_file(ems_event_path).to_crs(crs)

aoi_mask = rasterio.features.rasterize([(g, 1) for g in aoi_gdf.geometry if g is not None], out_shape=shape, transform=trans, fill=0, all_touched=False) == 1
ems_mask = rasterio.features.rasterize([(g, 1) for g in event_gdf.geometry if g is not None], out_shape=shape, transform=trans, fill=0, all_touched=False) == 1

pred = ((r == 2) | (r == 3)) & aoi_mask
gt = ems_mask & aoi_mask

tp = int(np.sum(pred & gt))
fp = int(np.sum(pred & ~gt))
fn = int(np.sum(~pred & gt))

iou = tp / (tp + fp + fn) if (tp + fp + fn) else 0.0
prec = tp / (tp + fp) if (tp + fp) else 0.0
rec = tp / (tp + fn) if (tp + fn) else 0.0
f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0

print(f"TP: {tp}, FP: {fp}, FN: {fn}")
print(f"IoU: {iou:.4f}, F1: {f1:.4f}, Precision: {prec:.4f}, Recall: {rec:.4f}")
