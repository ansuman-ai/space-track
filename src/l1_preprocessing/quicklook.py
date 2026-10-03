"""
Quick-look visualization generator for Layer 1 preprocessing.
Renders pre VV, post VV, log-ratio VV, HAND, and shadow/layover mask side-by-side.
"""

import os
from typing import Optional
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def render_quicklook(
    pre_vv_db: np.ndarray,
    post_vv_db: np.ndarray,
    log_ratio_vv: np.ndarray,
    hand: np.ndarray,
    shadow_layover_mask: np.ndarray,
    output_png_path: str,
    title_suffix: str = ""
) -> str:
    """
    Renders 5 side-by-side subplots and saves to output_png_path.
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_png_path)), exist_ok=True)

    fig, axes = plt.subplots(1, 5, figsize=(26, 6), constrained_layout=True)

    # 1. Pre VV
    im0 = axes[0].imshow(pre_vv_db, cmap="gray", vmin=-25.0, vmax=5.0)
    axes[0].set_title("Pre-Event VV (dB)\n[Lee Filtered 5x5]", fontsize=11, fontweight="bold")
    axes[0].axis("off")
    fig.colorbar(im0, ax=axes[0], orientation="horizontal", pad=0.03, shrink=0.75, label="dB")

    # 2. Post VV
    im1 = axes[1].imshow(post_vv_db, cmap="gray", vmin=-25.0, vmax=5.0)
    axes[1].set_title("Post-Event VV (dB)\n[Lee Filtered 5x5]", fontsize=11, fontweight="bold")
    axes[1].axis("off")
    fig.colorbar(im1, ax=axes[1], orientation="horizontal", pad=0.03, shrink=0.75, label="dB")

    # 3. Log-Ratio VV
    im2 = axes[2].imshow(log_ratio_vv, cmap="RdBu_r", vmin=-8.0, vmax=8.0)
    axes[2].set_title("Log-Ratio VV (dB)\n[Post - Pre]", fontsize=11, fontweight="bold")
    axes[2].axis("off")
    fig.colorbar(im2, ax=axes[2], orientation="horizontal", pad=0.03, shrink=0.75, label="Delta dB")

    # 4. HAND
    im3 = axes[3].imshow(hand, cmap="viridis", vmin=0.0, vmax=150.0)
    axes[3].set_title("HAND (m)\n[Height Above Nearest Drainage]", fontsize=11, fontweight="bold")
    axes[3].axis("off")
    fig.colorbar(im3, ax=axes[3], orientation="horizontal", pad=0.03, shrink=0.75, label="Meters")

    # 5. Shadow / Layover Mask
    im4 = axes[4].imshow(shadow_layover_mask, cmap="magma", vmin=0, vmax=1)
    axes[4].set_title("Shadow & Layover Mask\n[1 = Masked, 0 = Valid]", fontsize=11, fontweight="bold")
    axes[4].axis("off")
    fig.colorbar(im4, ax=axes[4], orientation="horizontal", pad=0.03, shrink=0.75, label="Binary Flag")

    suptitle = "Layer 1 Preprocessing Diagnostics"
    if title_suffix:
        suptitle += f" - {title_suffix}"
    fig.suptitle(suptitle, fontsize=14, fontweight="bold", y=1.02)

    plt.savefig(output_png_path, dpi=200, bbox_inches="tight")
    plt.close(fig)

    return output_png_path
