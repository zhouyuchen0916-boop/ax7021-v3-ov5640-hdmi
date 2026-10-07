from __future__ import annotations

import torch
from torch import Tensor, nn


INPUT_WIDTH = 160
INPUT_HEIGHT = 120
GRID_WIDTH = 20
GRID_HEIGHT = 15


class TinyFaceDetector(nn.Module):
    """Small fully-convolutional detector designed for an XC7Z020 datapath."""

    def __init__(self) -> None:
        super().__init__()
        self.conv1 = nn.Conv2d(1, 8, 3, stride=2, padding=1, bias=False)
        self.bn1 = nn.BatchNorm2d(8)
        self.conv2 = nn.Conv2d(8, 16, 3, stride=2, padding=1, bias=False)
        self.bn2 = nn.BatchNorm2d(16)
        self.conv3 = nn.Conv2d(16, 24, 3, stride=2, padding=1, bias=False)
        self.bn3 = nn.BatchNorm2d(24)
        self.head = nn.Conv2d(24, 5, 1, bias=True)
        self.relu = nn.ReLU(inplace=True)

    def forward(self, image: Tensor) -> Tensor:
        features = self.relu(self.bn1(self.conv1(image)))
        features = self.relu(self.bn2(self.conv2(features)))
        features = self.relu(self.bn3(self.conv3(features)))
        return self.head(features)


def count_macs() -> int:
    """Return multiply-accumulate operations for one 160x120 frame."""
    return (
        80 * 60 * 8 * 1 * 3 * 3
        + 40 * 30 * 16 * 8 * 3 * 3
        + 20 * 15 * 24 * 16 * 3 * 3
        + 20 * 15 * 5 * 24
    )


def decode_predictions(
    prediction: Tensor,
    confidence_threshold: float = 0.5,
) -> list[list[tuple[float, float, float, float, float]]]:
    """Decode grid output into normalized (x_min, y_min, x_max, y_max, score)."""
    if prediction.ndim != 4 or prediction.shape[1:] != (5, GRID_HEIGHT, GRID_WIDTH):
        raise ValueError(f"unexpected prediction shape: {tuple(prediction.shape)}")

    objectness = prediction[:, 0].sigmoid()
    box_values = prediction[:, 1:5].sigmoid()
    batches: list[list[tuple[float, float, float, float, float]]] = []
    for batch_index in range(prediction.shape[0]):
        boxes: list[tuple[float, float, float, float, float]] = []
        for grid_y in range(GRID_HEIGHT):
            for grid_x in range(GRID_WIDTH):
                score = float(objectness[batch_index, grid_y, grid_x])
                if score < confidence_threshold:
                    continue
                offset_x, offset_y, width, height = (
                    float(value)
                    for value in box_values[batch_index, :, grid_y, grid_x]
                )
                center_x = (grid_x + offset_x) / GRID_WIDTH
                center_y = (grid_y + offset_y) / GRID_HEIGHT
                boxes.append(
                    (
                        max(0.0, center_x - width / 2.0),
                        max(0.0, center_y - height / 2.0),
                        min(1.0, center_x + width / 2.0),
                        min(1.0, center_y + height / 2.0),
                        score,
                    )
                )
        batches.append(boxes)
    return batches
