"""
UNet Architecture with ResNet-18/34 Encoder for 6-channel SAR Flood Segmentation.
Pure PyTorch implementation with zero external vision library dependencies.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import List, Optional


class ConvBlock(nn.Module):
    """Two 3x3 convolutions with BatchNorm and ReLU."""

    def __init__(self, in_channels: int, out_channels: int):
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv2d(in_channels, out_channels, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True),
            nn.Conv2d(out_channels, out_channels, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.conv(x)


class BasicBlock(nn.Module):
    """Standard ResNet Basic Block."""

    expansion = 1

    def __init__(self, in_planes: int, planes: int, stride: int = 1):
        super().__init__()
        self.conv1 = nn.Conv2d(in_planes, planes, kernel_size=3, stride=stride, padding=1, bias=False)
        self.bn1 = nn.BatchNorm2d(planes)
        self.conv2 = nn.Conv2d(planes, planes, kernel_size=3, stride=1, padding=1, bias=False)
        self.bn2 = nn.BatchNorm2d(planes)

        self.shortcut = nn.Sequential()
        if stride != 1 or in_planes != self.expansion * planes:
            self.shortcut = nn.Sequential(
                nn.Conv2d(in_planes, self.expansion * planes, kernel_size=1, stride=stride, bias=False),
                nn.BatchNorm2d(self.expansion * planes)
            )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out = F.relu(self.bn1(self.conv1(x)))
        out = self.bn2(self.conv2(out))
        out += self.shortcut(x)
        return F.relu(out)


class DecoderBlock(nn.Module):
    """Upsampling followed by concatenation and double convolution."""

    def __init__(self, in_channels: int, skip_channels: int, out_channels: int):
        super().__init__()
        self.up = nn.Upsample(scale_factor=2, mode="bilinear", align_corners=True)
        self.conv = ConvBlock(in_channels + skip_channels, out_channels)

    def forward(self, x: torch.Tensor, skip: Optional[torch.Tensor] = None) -> torch.Tensor:
        x = self.up(x)
        if skip is not None:
            # Handle padding if dimensions differ slightly due to odd resolutions
            diff_y = skip.size(2) - x.size(2)
            diff_x = skip.size(3) - x.size(3)
            if diff_y != 0 or diff_x != 0:
                x = F.pad(x, [diff_x // 2, diff_x - diff_x // 2, diff_y // 2, diff_y - diff_y // 2])
            x = torch.cat([x, skip], dim=1)
        return self.conv(x)


class ResNetUNet(nn.Module):
    """
    UNet with ResNet-18 or ResNet-34 encoder.
    Accepts 6 input channels: [pre_vv, pre_vh, post_vv, post_vh, log_ratio, dem_slope].
    Outputs 1 logit channel for binary flood mask.
    """

    def __init__(
        self,
        in_channels: int = 6,
        num_classes: int = 1,
        encoder: str = "resnet18"
    ):
        super().__init__()
        self.in_channels = in_channels
        self.num_classes = num_classes

        # Layers configuration for ResNet18 vs ResNet34
        if encoder == "resnet34":
            num_blocks = [3, 4, 6, 3]
        else:  # default: resnet18
            num_blocks = [2, 2, 2, 2]

        # Initial stem: 6 channels -> 64
        self.in_planes = 64
        self.conv1 = nn.Conv2d(in_channels, 64, kernel_size=7, stride=2, padding=3, bias=False)
        self.bn1 = nn.BatchNorm2d(64)
        self.maxpool = nn.MaxPool2d(kernel_size=3, stride=2, padding=1)

        # Encoder stages
        self.layer1 = self._make_layer(BasicBlock, 64, num_blocks[0], stride=1)
        self.layer2 = self._make_layer(BasicBlock, 128, num_blocks[1], stride=2)
        self.layer3 = self._make_layer(BasicBlock, 256, num_blocks[2], stride=2)
        self.layer4 = self._make_layer(BasicBlock, 512, num_blocks[3], stride=2)

        # Decoder stages (skip connections from layer3, layer2, layer1, conv1)
        self.dec4 = DecoderBlock(512, 256, 256)
        self.dec3 = DecoderBlock(256, 128, 128)
        self.dec2 = DecoderBlock(128, 64, 64)
        self.dec1 = DecoderBlock(64, 64, 64)

        # Final upsampling to original input size
        self.final_up = nn.Upsample(scale_factor=2, mode="bilinear", align_corners=True)
        self.final_conv = nn.Sequential(
            nn.Conv2d(64, 32, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(32),
            nn.ReLU(inplace=True),
            nn.Conv2d(32, num_classes, kernel_size=1)
        )

    def _make_layer(self, block, planes: int, num_blocks: int, stride: int) -> nn.Sequential:
        strides = [stride] + [1] * (num_blocks - 1)
        layers = []
        for s in strides:
            layers.append(block(self.in_planes, planes, s))
            self.in_planes = planes * block.expansion
        return nn.Sequential(*layers)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # Encoder
        x0 = F.relu(self.bn1(self.conv1(x)))  # 1/2 resolution, 64 channels
        x_mp = self.maxpool(x0)               # 1/4 resolution, 64 channels
        x1 = self.layer1(x_mp)                # 1/4 resolution, 64 channels
        x2 = self.layer2(x1)                  # 1/8 resolution, 128 channels
        x3 = self.layer3(x2)                  # 1/16 resolution, 256 channels
        x4 = self.layer4(x3)                  # 1/32 resolution, 512 channels

        # Decoder with skips
        d4 = self.dec4(x4, x3)               # 1/16 resolution
        d3 = self.dec3(d4, x2)               # 1/8 resolution
        d2 = self.dec2(d3, x1)               # 1/4 resolution
        d1 = self.dec1(d2, x0)               # 1/2 resolution

        # Final head to original resolution
        d0 = self.final_up(d1)               # 1/1 original resolution
        logits = self.final_conv(d0)
        return logits
