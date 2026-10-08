from __future__ import annotations

import random
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import torch
from PIL import Image, ImageEnhance, ImageOps
from torch import Tensor
from torch.utils.data import Dataset

from .model import GRID_HEIGHT, GRID_WIDTH, INPUT_HEIGHT, INPUT_WIDTH


@dataclass(frozen=True)
class YoloFaceSample:
    image_path: Path
    boxes_cxcywh: tuple[tuple[float, float, float, float], ...]


def read_yolo_boxes(path: Path) -> tuple[tuple[float, float, float, float], ...]:
    boxes: list[tuple[float, float, float, float]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        fields = line.split()
        if len(fields) != 5:
            raise ValueError(f"{path}:{line_number}: expected 5 YOLO fields")
        class_id = int(fields[0])
        if class_id != 0:
            raise ValueError(f"{path}:{line_number}: expected face class 0, got {class_id}")
        center_x, center_y, width, height = (float(value) for value in fields[1:])
        if not (
            0.0 <= center_x <= 1.0
            and 0.0 <= center_y <= 1.0
            and 0.0 < width <= 1.0
            and 0.0 < height <= 1.0
        ):
            raise ValueError(f"{path}:{line_number}: YOLO box is outside normalized range")
        boxes.append((center_x, center_y, width, height))
    return tuple(boxes)


class YoloFaceGridDataset(Dataset[tuple[Tensor, Tensor]]):
    def __init__(
        self,
        image_root: Path,
        label_root: Path,
        augment: bool = False,
        min_face_pixels: float = 0.0,
        min_faces_per_image: int = 0,
        max_faces_per_image: int | None = None,
        require_all_faces_detectable: bool = False,
    ) -> None:
        samples: list[YoloFaceSample] = []
        for image_path in sorted(image_root.rglob("*")):
            if image_path.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
                continue
            relative = image_path.relative_to(image_root)
            label_path = (label_root / relative).with_suffix(".txt")
            if not label_path.exists():
                raise FileNotFoundError(f"missing label for {image_path}: {label_path}")
            boxes = read_yolo_boxes(label_path)
            if len(boxes) < min_faces_per_image:
                continue
            if max_faces_per_image is not None and len(boxes) > max_faces_per_image:
                continue
            detectable = [
                min(width * INPUT_WIDTH, height * INPUT_HEIGHT) >= min_face_pixels
                for _, _, width, height in boxes
            ]
            if require_all_faces_detectable and (not detectable or not all(detectable)):
                continue
            if not require_all_faces_detectable and min_face_pixels > 0.0 and not any(detectable):
                continue
            samples.append(YoloFaceSample(image_path, boxes))

        if not samples:
            raise ValueError(f"no usable YOLO samples found below {image_root}")
        self.samples = samples
        self.augment = augment
        self.min_face_pixels = min_face_pixels

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, index: int) -> tuple[Tensor, Tensor]:
        sample = self.samples[index]
        with Image.open(sample.image_path) as source:
            source = source.convert("L")
            boxes = list(sample.boxes_cxcywh)
            if self.augment and random.random() < 0.5:
                source = ImageOps.mirror(source)
                boxes = [(1.0 - cx, cy, width, height) for cx, cy, width, height in boxes]
            if self.augment:
                source = ImageEnhance.Brightness(source).enhance(random.uniform(0.8, 1.2))
                source = ImageEnhance.Contrast(source).enhance(random.uniform(0.8, 1.2))
            resized = source.resize((INPUT_WIDTH, INPUT_HEIGHT), Image.Resampling.BILINEAR)
            image_array = np.asarray(resized, dtype=np.float32).copy() / 255.0

        image_tensor = torch.from_numpy(image_array).unsqueeze(0)
        target = torch.zeros((5, GRID_HEIGHT, GRID_WIDTH), dtype=torch.float32)
        occupied_area = torch.zeros((GRID_HEIGHT, GRID_WIDTH), dtype=torch.float32)
        for center_x, center_y, width, height in boxes:
            if min(width * INPUT_WIDTH, height * INPUT_HEIGHT) < self.min_face_pixels:
                continue
            if not (0.0 <= center_x < 1.0 and 0.0 <= center_y < 1.0):
                continue
            grid_x = min(GRID_WIDTH - 1, int(center_x * GRID_WIDTH))
            grid_y = min(GRID_HEIGHT - 1, int(center_y * GRID_HEIGHT))
            area = width * height
            if area <= float(occupied_area[grid_y, grid_x]):
                continue
            occupied_area[grid_y, grid_x] = area
            target[0, grid_y, grid_x] = 1.0
            target[1, grid_y, grid_x] = center_x * GRID_WIDTH - grid_x
            target[2, grid_y, grid_x] = center_y * GRID_HEIGHT - grid_y
            target[3, grid_y, grid_x] = width
            target[4, grid_y, grid_x] = height
        return image_tensor, target
