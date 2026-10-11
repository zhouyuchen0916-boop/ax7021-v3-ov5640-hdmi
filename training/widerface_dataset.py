from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import random

import numpy as np
import torch
from PIL import Image, ImageEnhance, ImageOps
from torch import Tensor
from torch.utils.data import Dataset

from .model import GRID_HEIGHT, GRID_WIDTH, INPUT_HEIGHT, INPUT_WIDTH


@dataclass(frozen=True)
class WiderFaceAnnotation:
    box_xywh: tuple[float, float, float, float]
    blur: int = 0
    expression: int = 0
    illumination: int = 0
    invalid: int = 0
    occlusion: int = 0
    pose: int = 0

    @property
    def is_clear_full_face(self) -> bool:
        return (
            self.blur == 0
            and self.invalid == 0
            and self.occlusion == 0
            and self.pose == 0
        )


@dataclass(frozen=True)
class WiderFaceSample:
    relative_path: str
    annotations: tuple[WiderFaceAnnotation, ...]

    @property
    def boxes_xywh(self) -> tuple[tuple[float, float, float, float], ...]:
        return tuple(annotation.box_xywh for annotation in self.annotations)


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
        annotations: list[WiderFaceAnnotation] = []
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
                flags = [int(value) for value in fields[4:10]]
                flags.extend([0] * (6 - len(flags)))
                annotations.append(
                    WiderFaceAnnotation(
                        (x, y, width, height),
                        blur=flags[0],
                        expression=flags[1],
                        illumination=flags[2],
                        invalid=flags[3],
                        occlusion=flags[4],
                        pose=flags[5],
                    )
                )
        samples.append(WiderFaceSample(relative_path, tuple(annotations)))
    return samples


class WiderFaceGridDataset(Dataset[tuple[Tensor, Tensor]]):
    def __init__(
        self,
        image_root: Path,
        annotation_file: Path,
        augment: bool = False,
        min_face_pixels: float = 0.0,
        min_faces_per_image: int = 0,
        max_faces_per_image: int | None = None,
        require_detectable_face: bool = False,
        require_all_faces_detectable: bool = False,
        clean_full_faces_only: bool = False,
        include_empty_images: bool = False,
    ) -> None:
        self.image_root = image_root
        samples = parse_widerface_annotations(annotation_file)
        if min_faces_per_image > 0:
            samples = [
                sample
                for sample in samples
                if (
                    include_empty_images
                    and not sample.annotations
                )
                or len(sample.annotations) >= min_faces_per_image
            ]
        if max_faces_per_image is not None:
            samples = [
                sample
                for sample in samples
                if len(sample.annotations) <= max_faces_per_image
            ]
        if clean_full_faces_only:
            samples = [
                sample
                for sample in samples
                if (
                    include_empty_images
                    and not sample.annotations
                )
                or (
                    sample.annotations
                    and all(
                        annotation.is_clear_full_face
                        for annotation in sample.annotations
                    )
                )
            ]
        if (require_detectable_face or require_all_faces_detectable) and min_face_pixels > 0.0:
            detectable_samples: list[WiderFaceSample] = []
            for sample in samples:
                if include_empty_images and not sample.annotations:
                    detectable_samples.append(sample)
                    continue
                with Image.open(image_root / sample.relative_path) as source:
                    source_width, source_height = source.size
                detectable = [
                    min(
                        width * INPUT_WIDTH / source_width,
                        height * INPUT_HEIGHT / source_height,
                    )
                    >= min_face_pixels
                    for _, _, width, height in sample.boxes_xywh
                ]
                if (
                    require_all_faces_detectable
                    and detectable
                    and all(detectable)
                ) or (
                    require_detectable_face
                    and not require_all_faces_detectable
                    and any(detectable)
                ):
                    detectable_samples.append(sample)
            samples = detectable_samples
        self.samples = samples
        self.augment = augment
        self.min_face_pixels = min_face_pixels

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, index: int) -> tuple[Tensor, Tensor]:
        sample = self.samples[index]
        image_path = self.image_root / sample.relative_path
        with Image.open(image_path) as source:
            source = source.convert("L")
            source_width, source_height = source.size
            boxes = list(sample.boxes_xywh)
            if self.augment and random.random() < 0.5:
                source = ImageOps.mirror(source)
                boxes = [
                    (source_width - x - width, y, width, height)
                    for x, y, width, height in boxes
                ]
            if self.augment:
                source = ImageEnhance.Brightness(source).enhance(random.uniform(0.8, 1.2))
                source = ImageEnhance.Contrast(source).enhance(random.uniform(0.8, 1.2))
            resized = source.resize((INPUT_WIDTH, INPUT_HEIGHT), Image.Resampling.BILINEAR)
            image_array = np.asarray(resized, dtype=np.float32).copy() / 255.0

        image_tensor = torch.from_numpy(image_array).unsqueeze(0)
        target = torch.zeros((5, GRID_HEIGHT, GRID_WIDTH), dtype=torch.float32)
        occupied_area = torch.zeros((GRID_HEIGHT, GRID_WIDTH), dtype=torch.float32)

        for x, y, width, height in boxes:
            resized_width = width * INPUT_WIDTH / source_width
            resized_height = height * INPUT_HEIGHT / source_height
            if min(resized_width, resized_height) < self.min_face_pixels:
                continue
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
