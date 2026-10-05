import os
import glob
import numpy as np
import rasterio
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

def make_rgb(npz_path):
    z = np.load(npz_path)
    r = z['B04'].astype(np.float32)
    g = z['B03'].astype(np.float32)
    b = z['B02'].astype(np.float32)
    
    # Clip and normalize 2-98%
    rgb = np.stack([r, g, b], axis=-1)
    p2 = np.percentile(rgb[rgb > 0], 2) if np.any(rgb > 0) else 0
    p98 = np.percentile(rgb[rgb > 0], 98) if np.any(rgb > 0) else 4000
    rgb_norm = np.clip((rgb - p2) / (p98 - p2 + 1e-6), 0.0, 1.0)
    return rgb_norm

def create_quicklook(npz_path, mask_tif_path, out_png_path, title):
    rgb = make_rgb(npz_path)
    
    with rasterio.open(mask_tif_path) as s:
        mask = s.read(1)
        
    fig, ax = plt.subplots(figsize=(10, 12), dpi=150)
    ax.imshow(rgb)
    
    # Overlay permanent water (class 1)
    pw_mask = (mask == 1)
    if np.any(pw_mask):
        pw_overlay = np.zeros((*mask.shape, 4), dtype=np.float32)
        pw_overlay[pw_mask] = [0.0, 0.8, 1.0, 0.7] # Cyan
        ax.imshow(pw_overlay)
        
    # Overlay flood (class 2)
    fl_mask = (mask == 2)
    if np.any(fl_mask):
        fl_overlay = np.zeros((*mask.shape, 4), dtype=np.float32)
        fl_overlay[fl_mask] = [1.0, 0.1, 0.1, 0.85] # Red
        ax.imshow(fl_overlay)
        
    ax.set_title(title, fontsize=14, fontweight='bold', pad=12)
    ax.axis('off')
    
    legend_patches = [
        mpatches.Patch(color='#00CCFF', label=f'Permanent Water (class 1, n={int(np.sum(pw_mask))})'),
        mpatches.Patch(color='#FF1A1A', label=f'Flooded Water (class 2, n={int(np.sum(fl_mask))})')
    ]
    ax.legend(handles=legend_patches, loc='lower right', framealpha=0.85, fontsize=10)
    
    plt.tight_layout()
    os.makedirs(os.path.dirname(out_png_path), exist_ok=True)
    plt.savefig(out_png_path, bbox_inches='tight')
    plt.close()
    print(f"Saved quicklook to {out_png_path}")

if __name__ == "__main__":
    import sys
    npz = sys.argv[1]
    mask = sys.argv[2]
    out = sys.argv[3]
    t = sys.argv[4] if len(sys.argv) > 4 else "Quicklook"
    create_quicklook(npz, mask, out, t)
