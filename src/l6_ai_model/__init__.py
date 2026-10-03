"""
Layer 6: AI Flood Segmentation Model Module
Deep learning segmentation for Sentinel-1 pre/post + DEM slope.
Trained on Kuro Siwo event splits.
"""

from .dataset import KuroSiwoDataset
from .model import ResNetUNet
from .predict import predict

__all__ = ["KuroSiwoDataset", "ResNetUNet", "predict"]
