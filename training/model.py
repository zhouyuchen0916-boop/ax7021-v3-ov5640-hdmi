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
        self.context1_dw = nn.Conv2d(
            24, 24, 3, padding=2, dilation=2, groups=24, bias=False
        )
        self.context1_dw_bn = nn.BatchNorm2d(24)
        self.context1_pw = nn.Conv2d(24, 24, 1, bias=False)
        self.context1_pw_bn = nn.BatchNorm2d(24)
        self.context2_dw = nn.Conv2d(
            24, 24, 3, padding=4, dilation=4, groups=24, bias=False
        )
        self.context2_dw_bn = nn.BatchNorm2d(24)
        self.context2_pw = nn.Conv2d(24, 24, 1, bias=False)
        self.context2_pw_bn = nn.BatchNorm2d(24)
        self.head = nn.Conv2d(24, 5, 1, bias=True)
        self.relu = nn.ReLU(inplace=True)

    def forward(self, image: Tensor) -> Tensor:
        features = self.relu(self.bn1(self.conv1(image)))
        features = self.relu(self.bn2(self.conv2(features)))
        features = self.relu(self.bn3(self.conv3(features)))
        features = self.relu(self.context1_dw_bn(self.context1_dw(features)))
        features = self.relu(self.context1_pw_bn(self.context1_pw(features)))
        features = self.relu(self.context2_dw_bn(self.context2_dw(features)))
        features = self.relu(self.context2_pw_bn(self.context2_pw(features)))
        return self.head(features)


def count_macs() -> int:
    """Return multiply-accumulate operations for one 160x120 frame."""
    return (
        80 * 60 * 8 * 1 * 3 * 3
        + 40 * 30 * 16 * 8 * 3 * 3
        + 20 * 15 * 24 * 16 * 3 * 3
        + 20 * 15 * 24 * 1 * 3 * 3
        + 20 * 15 * 24 * 24
        + 20 * 15 * 24 * 1 * 3 * 3
        + 20 * 15 * 24 * 24
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


def box_iou(
    first: tuple[float, float, float, float, float],
    second: tuple[float, float, float, float, float],
) -> float:
    """Return intersection-over-union for two decoded boxes."""
    left = max(first[0], second[0])
    top = max(first[1], second[1])
    right = min(first[2], second[2])
    bottom = min(first[3], second[3])
    intersection = max(0.0, right - left) * max(0.0, bottom - top)
    first_area = max(0.0, first[2] - first[0]) * max(0.0, first[3] - first[1])
    second_area = max(0.0, second[2] - second[0]) * max(0.0, second[3] - second[1])
    union = first_area + second_area - intersection
    return intersection / union if union > 0.0 else 0.0


def non_max_suppression(
    boxes: list[tuple[float, float, float, float, float]],
    iou_threshold: float = 0.35,
    max_detections: int = 10,
) -> list[tuple[float, float, float, float, float]]:
    """Suppress overlapping boxes, keeping the highest confidence first."""
    remaining = sorted(boxes, key=lambda box: box[4], reverse=True)
    selected: list[tuple[float, float, float, float, float]] = []
    while remaining and len(selected) < max_detections:
        best = remaining.pop(0)
        selected.append(best)
        remaining = [box for box in remaining if box_iou(best, box) < iou_threshold]
    return selected
