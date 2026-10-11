from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import torch
from PIL import Image

from .model import INPUT_HEIGHT, INPUT_WIDTH, TinyFaceDetector, decode_predictions, non_max_suppression


def main() -> None:
    parser = argparse.ArgumentParser(description="Measure false detections on zero-face images.")
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("--images", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    paths = sorted(
        path
        for path in args.images.iterdir()
        if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg"}
    )
    tensors: list[torch.Tensor] = []
    for path in paths:
        with Image.open(path) as source:
            grayscale = source.convert("L").resize(
                (INPUT_WIDTH, INPUT_HEIGHT), Image.Resampling.BILINEAR
            )
        values = np.asarray(grayscale, dtype=np.float32).copy() / 255.0
        tensors.append(torch.from_numpy(values).unsqueeze(0))

    checkpoint = torch.load(args.checkpoint, map_location="cpu", weights_only=True)
    model = TinyFaceDetector()
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()
    predictions: list[torch.Tensor] = []
    with torch.inference_mode():
        for start in range(0, len(tensors), 64):
            predictions.extend(model(torch.stack(tensors[start : start + 64])))

    results: list[dict[str, float | int]] = []
    for threshold_value in range(80, 100, 2):
        threshold = threshold_value / 100.0
        images_with_false_detection = 0
        total_false_detections = 0
        false_image_names: list[str] = []
        for path, raw_prediction in zip(paths, predictions):
            decoded = decode_predictions(raw_prediction.unsqueeze(0), threshold)[0]
            selected = non_max_suppression(decoded, iou_threshold=0.35, max_detections=10)
            total_false_detections += len(selected)
            images_with_false_detection += int(bool(selected))
            if selected:
                false_image_names.append(path.name)
        result = {
            "threshold": threshold,
            "images": len(paths),
            "images_with_false_detection": images_with_false_detection,
            "total_false_detections": total_false_detections,
            "false_image_rate": images_with_false_detection / max(1, len(paths)),
            "false_image_names": false_image_names,
        }
        results.append(result)
        print(
            f"threshold={threshold:.2f} false_images={images_with_false_detection}/{len(paths)} "
            f"false_boxes={total_false_detections} "
            f"false_image_rate={result['false_image_rate']:.4f}"
        )
        if threshold >= 0.96 and false_image_names:
            print("FALSE_IMAGE_NAMES=" + ",".join(false_image_names))

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(
                {
                    "checkpoint": str(args.checkpoint),
                    "trained_epochs": int(checkpoint.get("trained_epochs", 0)),
                    "results": results,
                },
                indent=2,
            ),
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
