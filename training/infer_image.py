from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import torch
from PIL import Image, ImageDraw

from .model import (
    INPUT_HEIGHT,
    INPUT_WIDTH,
    TinyFaceDetector,
    decode_predictions,
    non_max_suppression,
)


def load_input(image_path: Path) -> tuple[Image.Image, torch.Tensor]:
    source = Image.open(image_path).convert("RGB")
    grayscale = source.convert("L").resize(
        (INPUT_WIDTH, INPUT_HEIGHT), Image.Resampling.BILINEAR
    )
    values = np.asarray(grayscale, dtype=np.float32).copy() / 255.0
    return source, torch.from_numpy(values).unsqueeze(0).unsqueeze(0)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run TinyFaceDetector on one image.")
    parser.add_argument("image", type=Path)
    parser.add_argument("--checkpoint", type=Path, default=Path("training/outputs/tiny_face.pt"))
    parser.add_argument("--output", type=Path, default=Path("training/outputs/inference.png"))
    parser.add_argument("--threshold", type=float, default=0.6)
    parser.add_argument("--nms-iou", type=float, default=0.35)
    parser.add_argument("--max-detections", type=int, default=10)
    args = parser.parse_args()

    checkpoint = torch.load(args.checkpoint, map_location="cpu", weights_only=True)
    model = TinyFaceDetector()
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()

    source, image_tensor = load_input(args.image)
    with torch.inference_mode():
        prediction = model(image_tensor)
    decoded = decode_predictions(prediction, args.threshold)[0]
    boxes = non_max_suppression(decoded, args.nms_iou, args.max_detections)

    draw = ImageDraw.Draw(source)
    width, height = source.size
    for x_min, y_min, x_max, y_max, score in boxes:
        coordinates = (
            round(x_min * width),
            round(y_min * height),
            round(x_max * width),
            round(y_max * height),
        )
        line_width = max(2, round(min(width, height) / 240))
        draw.rectangle(coordinates, outline=(0, 255, 0), width=line_width)
        draw.text((coordinates[0] + 2, coordinates[1] + 2), f"{score:.2f}", fill=(0, 255, 0))
        print(
            f"BOX x0={coordinates[0]} y0={coordinates[1]} "
            f"x1={coordinates[2]} y1={coordinates[3]} score={score:.6f}"
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    source.save(args.output)
    print(f"DETECTIONS={len(boxes)}")
    print(f"OUTPUT={args.output}")


if __name__ == "__main__":
    main()
