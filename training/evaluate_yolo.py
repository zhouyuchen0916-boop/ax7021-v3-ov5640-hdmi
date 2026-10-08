from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch
from torch import Tensor
from torch.utils.data import DataLoader

from .model import (
    GRID_HEIGHT,
    GRID_WIDTH,
    TinyFaceDetector,
    box_iou,
    decode_predictions,
    non_max_suppression,
)
from .yolo_face_dataset import YoloFaceGridDataset


def decode_targets(target: Tensor) -> list[list[tuple[float, float, float, float, float]]]:
    batches: list[list[tuple[float, float, float, float, float]]] = []
    for batch_index in range(target.shape[0]):
        boxes: list[tuple[float, float, float, float, float]] = []
        for grid_y in range(GRID_HEIGHT):
            for grid_x in range(GRID_WIDTH):
                if float(target[batch_index, 0, grid_y, grid_x]) <= 0.5:
                    continue
                offset_x, offset_y, width, height = (
                    float(value) for value in target[batch_index, 1:5, grid_y, grid_x]
                )
                center_x = (grid_x + offset_x) / GRID_WIDTH
                center_y = (grid_y + offset_y) / GRID_HEIGHT
                boxes.append(
                    (
                        max(0.0, center_x - width / 2.0),
                        max(0.0, center_y - height / 2.0),
                        min(1.0, center_x + width / 2.0),
                        min(1.0, center_y + height / 2.0),
                        1.0,
                    )
                )
        batches.append(boxes)
    return batches


def match_boxes(
    predicted: list[tuple[float, float, float, float, float]],
    target: list[tuple[float, float, float, float, float]],
    iou_threshold: float,
) -> tuple[int, int, int]:
    unmatched = set(range(len(target)))
    true_positive = 0
    for prediction in sorted(predicted, key=lambda box: box[4], reverse=True):
        candidates = [(box_iou(prediction, target[index]), index) for index in unmatched]
        overlap, best_index = max(candidates, default=(0.0, -1))
        if overlap >= iou_threshold:
            true_positive += 1
            unmatched.remove(best_index)
    false_positive = len(predicted) - true_positive
    false_negative = len(unmatched)
    return true_positive, false_positive, false_negative


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate TinyFace on a YOLO face dataset.")
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("--images", type=Path, required=True)
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument("--iou", type=float, default=0.3)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    dataset = YoloFaceGridDataset(
        args.images,
        args.labels,
        augment=False,
        min_face_pixels=16,
        min_faces_per_image=1,
        max_faces_per_image=3,
        require_all_faces_detectable=True,
    )
    loader = DataLoader(dataset, batch_size=64, num_workers=0)
    checkpoint = torch.load(args.checkpoint, map_location="cpu", weights_only=True)
    model = TinyFaceDetector()
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()

    predictions: list[Tensor] = []
    targets: list[list[tuple[float, float, float, float, float]]] = []
    with torch.inference_mode():
        for images, batch_targets in loader:
            predictions.extend(model(images))
            targets.extend(decode_targets(batch_targets))

    thresholds = [value / 100.0 for value in range(50, 100, 2)]
    results: list[dict[str, float | int]] = []
    for threshold in thresholds:
        true_positive = false_positive = false_negative = 0
        for raw_prediction, target in zip(predictions, targets):
            decoded = decode_predictions(raw_prediction.unsqueeze(0), threshold)[0]
            selected = non_max_suppression(decoded, iou_threshold=0.35, max_detections=10)
            tp, fp, fn = match_boxes(selected, target, args.iou)
            true_positive += tp
            false_positive += fp
            false_negative += fn
        precision = true_positive / max(1, true_positive + false_positive)
        recall = true_positive / max(1, true_positive + false_negative)
        f1_score = 2.0 * precision * recall / max(1e-12, precision + recall)
        result = {
            "threshold": threshold,
            "true_positive": true_positive,
            "false_positive": false_positive,
            "false_negative": false_negative,
            "precision": precision,
            "recall": recall,
            "f1": f1_score,
        }
        results.append(result)
        print(
            f"threshold={threshold:.2f} precision={precision:.4f} "
            f"recall={recall:.4f} f1={f1_score:.4f} tp={true_positive} "
            f"fp={false_positive} fn={false_negative}"
        )

    best = max(results, key=lambda result: float(result["f1"]))
    print("BEST=" + json.dumps(best, ensure_ascii=False))
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(
                {
                    "checkpoint": str(args.checkpoint),
                    "trained_epochs": int(checkpoint.get("trained_epochs", 0)),
                    "iou_threshold": args.iou,
                    "samples": len(dataset),
                    "results": results,
                    "best": best,
                },
                indent=2,
            ),
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
