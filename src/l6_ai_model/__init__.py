"""
Layer 6: AI Flood Segmentation Model Module
Deep learning segmentation for Sentinel-1 pre/post + DEM slope.
Trained on Kuro Siwo event splits with SNUNet-CD.
"""

from .model import SNUNet_ECAM, load_model
from .predict import predict

__all__ = ["SNUNet_ECAM", "load_model", "predict"]
