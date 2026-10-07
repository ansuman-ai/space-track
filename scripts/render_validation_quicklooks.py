import sys, os
from pathlib import Path
import numpy as np
import rasterio
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D
from scipy.ndimage import label

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))
from src.common.plot_utils import plot_raster_background
from src.l2_detection.flat_floodplain import otsu_threshold

def render_event_quicklook(
    run_dir,
    aoi_shp,
    event_shp,
    title,
    out_png,
    t_water_val=-13.0,
    min_blob=20
):
    interim = Path(run_dir) / 'interim'
    with rasterio.open(interim / 'post_vv.tif') as src:
        post_vv = src.read(1)
        transform = src.transform
        bounds = (src.bounds.left, src.bounds.bottom, src.bounds.right, src.bounds.top)
        crs = src.crs
    with rasterio.open(interim / 'pre_vv.tif') as src:
        pre_vv = src.read(1)
    with rasterio.open(interim / 'hand.tif') as src:
        hand = src.read(1)

    # Stream mask
    stream_mask_path = interim / 'stream_mask.tif'
    stream_arr = None
    if stream_mask_path.exists():
        with rasterio.open(stream_mask_path) as src_s:
            stream_arr = src_s.read(1)

    # Read EMS AOI and Ground Truth
    aoi_gdf = gpd.read_file(aoi_shp).to_crs(crs)
    ev_gdf = gpd.read_file(event_shp).to_crs(crs)

    finite_mask = np.isfinite(post_vv) & np.isfinite(pre_vv)
    if t_water_val is None:
        t_water = otsu_threshold(post_vv[finite_mask])
    else:
        t_water = t_water_val

    # Standard flat flood detector
    cand = (post_vv < t_water) & (pre_vv >= t_water) & (hand <= 15.0) & finite_mask
    if min_blob > 0:
        lbl, num = label(cand)
        counts = np.bincount(lbl.ravel())
        large = np.isin(lbl, np.where(counts >= min_blob)[0][1:])
        cand = large

    fig, ax = plt.subplots(figsize=(10, 8), dpi=200)

    # 1. Raster Background (S1 Post VV dB)
    plot_raster_background(
        ax=ax,
        raster_source=post_vv,
        transform=transform,
        bounds=bounds,
        cmap="gray",
        vmin=-25.0,
        vmax=0.0,
        zorder=1
    )

    # 2. Plot River centerline for alignment
    if stream_arr is not None and np.any(stream_arr == 1):
        extent = (bounds[0], bounds[2], bounds[1], bounds[3])
        masked_stream = np.ma.masked_where(stream_arr != 1, stream_arr)
        ax.imshow(masked_stream, extent=extent, origin="upper", cmap="Blues", alpha=0.9, zorder=3)

    # 3. Plot Pipeline Detected Flood (Visible Royal Blue Fill)
    extent = (bounds[0], bounds[2], bounds[1], bounds[3])
    if np.any(cand):
        masked_cand = np.ma.masked_where(~cand, cand)
        ax.imshow(masked_cand, extent=extent, origin="upper", cmap="cool", alpha=0.65, zorder=4)

    # 4. Plot EMS Observed Event Flood Outline (Bright Red)
    ev_gdf.boundary.plot(ax=ax, color="#ff1744", linewidth=1.5, zorder=5)

    # 5. Plot AOI Boundary (Yellow dashed)
    aoi_gdf.boundary.plot(ax=ax, color="#ffd600", linewidth=1.5, linestyle="--", zorder=6)

    # Zoom to AOI extent with 5% margin
    aoi_bounds = aoi_gdf.total_bounds
    pad_x = (aoi_bounds[2] - aoi_bounds[0]) * 0.05
    pad_y = (aoi_bounds[3] - aoi_bounds[1]) * 0.05
    ax.set_xlim(aoi_bounds[0] - pad_x, aoi_bounds[2] + pad_x)
    ax.set_ylim(aoi_bounds[1] - pad_y, aoi_bounds[3] + pad_y)

    ax.set_title(title, fontsize=12, fontweight="bold", pad=10)
    ax.set_xlabel("UTM Easting (m)", fontsize=9)
    ax.set_ylabel("UTM Northing (m)", fontsize=9)

    # Legend
    legend_elements = [
        mpatches.Patch(edgecolor="#ffd600", facecolor="none", linestyle="--", linewidth=1.5, label="Copernicus EMS AOI"),
        Line2D([0], [0], color="#ff1744", linewidth=1.8, label="EMS Ground Truth Flood Outline"),
        Line2D([0], [0], color="#00e5ff", linewidth=1.5, label="River Centerline Alignment"),
        mpatches.Patch(color="#00e5ff", alpha=0.7, label=f"Pipeline Detected Flood (VV < {t_water:.1f} dB)")
    ]
    ax.legend(handles=legend_elements, loc="upper right", framealpha=0.85, fontsize=8)

    plt.tight_layout()
    Path(out_png).parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_png, dpi=200, bbox_inches="tight")
    plt.close()
    print(f"Saved quicklook to {out_png}")

if __name__ == '__main__':
    art_dir = os.environ.get('ARTIFACTS_DIR', str(ROOT_DIR / 'scratch'))

    # Italy EMSR659 AOI01 (Largest flood area in Emilia-Romagna)
    render_event_quicklook(
        run_dir='runs/emsr659_aoi01_val',
        aoi_shp='validation/emsr659/EMSR659_AOI01_DEL_PRODUCT_v2/EMSR659_AOI01_DEL_PRODUCT_v2/EMSR659_AOI01_DEL_PRODUCT_areaOfInterestA_v2.shp',
        event_shp='validation/emsr659/EMSR659_AOI01_DEL_PRODUCT_v2/EMSR659_AOI01_DEL_PRODUCT_v2/EMSR659_AOI01_DEL_PRODUCT_observedEventA_v2.shp',
        title='EMSR659 AOI01: Emilia-Romagna (Italy, May 2023) Validation',
        out_png=f'{art_dir}/quicklook_emsr659_italy.png',
        t_water_val=-13.0
    )

    # Greece EMSR692 AOI02
    render_event_quicklook(
        run_dir='runs/emsr692_val',
        aoi_shp='validation/emsr692/EMSR692_AOI02_DEL_PRODUCT_areaOfInterestA_v2.shp',
        event_shp='validation/emsr692/EMSR692_AOI02_DEL_PRODUCT_observedEventA_v2.shp',
        title='EMSR692 AOI02: Storm Daniel Thessaly Plain (Greece, Sept 2023) Validation',
        out_png=f'{art_dir}/quicklook_emsr692_greece.png',
        t_water_val=-13.0
    )
