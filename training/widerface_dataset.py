from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from torch import Tensor
from torch.utils.data import Dataset

from .model import GRID_HEIGHT, GRID_WIDTH, INPUT_HEIGHT, INPUT_WIDTH


@dataclass(frozen=True)
class WiderFaceSample:
    relative_path: str
    boxes_xywh: tuple[tuple[float, float, float, float], ...]


def parse_widerface_annotations(path: Path) -> list[WiderFaceSample]:
    lines = path.read_text(encoding="utf-8").splitlines()
    samples: list[WiderFaceSample] = []
    index = 0
    while index < len(lines):
        relative_path = lines[index].strip()
        index += 1
        if not relative_path:
            continue
        if index >= len(lines):
            raise ValueError(f"missing face count after {relative_path}")
        face_count = int(lines[index].strip())
        index += 1
        boxes: list[tuple[float, float, float, float]] = []
        # The official WIDER FACE text files keep one all-zero placeholder
        # box after some images whose face count is zero.  It is not included
        # in face_count, so consume it explicitly before reading the next path.
        if face_count == 0 and index < len(lines):
            placeholder_fields = lines[index].split()
            if len(placeholder_fields) >= 4:
                try:
                    placeholder_box = tuple(float(value) for value in placeholder_fields[:4])
                except ValueError:
                    placeholder_box = ()
                if placeholder_box == (0.0, 0.0, 0.0, 0.0):
                    index += 1
        for _ in range(face_count):
            if index >= len(lines):
                raise ValueError(f"truncated annotation for {relative_path}")
            fields = lines[index].split()
            index += 1
            if len(fields) < 4:
                raise ValueError(f"invalid annotation line for {relative_path}")
            x, y, width, height = (float(value) for value in fields[:4])
            if width > 1.0 and height > 1.0:
                boxes.append((x, y, width, height))
        samples.append(WiderFaceSample(relative_path, tuple(boxes)))
    return samples


class WiderFaceGridDataset(Dataset[tuple[Tensor, Tensor]]):
    def __init__(self, image_root: Path, annotation_file: Path) -> None:
        self.image_root = image_root
        self.samples = parse_widerface_annotations(annotation_file)

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, index: int) -> tuple[Tensor, Tensor]:
        sample = self.samples[index]
        image_path = self.image_root / sample.relative_path
        with Image.open(image_path) as source:
            source = source.convert("L")
            source_width, source_height = source.size
            resized = source.resize((INPUT_WIDTH, INPUT_HEIGHT), Image.Resampling.BILINEAR)
            image_array = np.asarray(resized, dtype=np.float32).copy() / 255.0

        image_tensor = torch.from_numpy(image_array).unsqueeze(0)
        target = torch.zeros((5, GRID_HEIGHT, GRID_WIDTH), dtype=torch.float32)
        occupied_area = torch.zeros((GRID_HEIGHT, GRID_WIDTH), dtype=torch.float32)

        for x, y, width, height in sample.boxes_xywh:
            center_x = (x + width / 2.0) / source_width
            center_y = (y + height / 2.0) / source_height
            norm_width = width / source_width
            norm_height = height / source_height
            if not (0.0 <= center_x < 1.0 and 0.0 <= center_y < 1.0):
                continue
            grid_x = min(GRID_WIDTH - 1, int(center_x * GRID_WIDTH))
            grid_y = min(GRID_HEIGHT - 1, int(center_y * GRID_HEIGHT))
            area = norm_width * norm_height
            if area <= float(occupied_area[grid_y, grid_x]):
                continue
            occupied_area[grid_y, grid_x] = area
            target[0, grid_y, grid_x] = 1.0
            target[1, grid_y, grid_x] = center_x * GRID_WIDTH - grid_x
            target[2, grid_y, grid_x] = center_y * GRID_HEIGHT - grid_y
            target[3, grid_y, grid_x] = min(1.0, norm_width)
            target[4, grid_y, grid_x] = min(1.0, norm_height)

        return image_tensor, target
