from __future__ import annotations

import argparse
import random
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as functional
from torch import Tensor
from torch.utils.data import DataLoader, Subset

from .model import TinyFaceDetector, count_macs
from .widerface_dataset import WiderFaceGridDataset


def detection_loss(
    prediction: Tensor,
    target: Tensor,
    positive_weight: float = 128.0,
) -> tuple[Tensor, Tensor, Tensor]:
    positive = target[:, 0] > 0.5
    objectness_loss = functional.binary_cross_entropy_with_logits(
        prediction[:, 0],
        target[:, 0],
        pos_weight=prediction.new_tensor(positive_weight),
    )
    if positive.any():
        predicted_boxes = prediction[:, 1:5].sigmoid().permute(0, 2, 3, 1)[positive]
        target_boxes = target[:, 1:5].permute(0, 2, 3, 1)[positive]
        box_loss = functional.smooth_l1_loss(predicted_boxes, target_boxes)
    else:
        box_loss = prediction.sum() * 0.0
    total = objectness_loss + 5.0 * box_loss
    return total, objectness_loss, box_loss


def evaluate(
    model: TinyFaceDetector,
    loader: DataLoader,
    device: torch.device,
    threshold: float = 0.6,
    positive_weight: float = 128.0,
) -> tuple[float, float, float, float]:
    model.eval()
    loss_sum = 0.0
    true_positive = 0
    false_positive = 0
    false_negative = 0
    with torch.inference_mode():
        for images, targets in loader:
            images = images.to(device)
            targets = targets.to(device)
            predictions = model(images)
            total, _, _ = detection_loss(predictions, targets, positive_weight)
            loss_sum += float(total)
            predicted_positive = predictions[:, 0].sigmoid() >= threshold
            target_positive = targets[:, 0] > 0.5
            true_positive += int((predicted_positive & target_positive).sum())
            false_positive += int((predicted_positive & ~target_positive).sum())
            false_negative += int((~predicted_positive & target_positive).sum())

    precision = true_positive / max(1, true_positive + false_positive)
    recall = true_positive / max(1, true_positive + false_negative)
    f1_score = 2.0 * precision * recall / max(1e-12, precision + recall)
    return loss_sum / max(1, len(loader)), precision, recall, f1_score


def save_checkpoint(
    path: Path,
    model: TinyFaceDetector,
    epoch: int,
    validation_loss: float,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    cpu_state = {name: value.detach().cpu() for name, value in model.state_dict().items()}
    torch.save(
        {
            "model_state_dict": cpu_state,
            "input_shape": [1, 1, 120, 160],
            "output_shape": [1, 5, 15, 20],
            "trained_epochs": epoch,
            "validation_loss": validation_loss,
            "architecture": "TinyFaceDetectorContext",
        },
        path,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the AX7021 160x120 face detector.")
    parser.add_argument("--images", type=Path, required=True)
    parser.add_argument("--annotations", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("training/outputs/tiny_face.pt"))
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--learning-rate", type=float, default=1e-3)
    parser.add_argument("--workers", type=int, default=0)
    parser.add_argument("--seed", type=int, default=7021)
    parser.add_argument("--validation-samples", type=int, default=512)
    parser.add_argument("--min-face-pixels", type=float, default=16.0)
    parser.add_argument("--min-faces-per-image", type=int, default=1)
    parser.add_argument("--max-faces-per-image", type=int, default=3)
    parser.add_argument("--clean-full-faces-only", action="store_true")
    parser.add_argument("--require-all-faces-detectable", action="store_true")
    parser.add_argument("--positive-weight", type=float, default=128.0)
    args = parser.parse_args()

    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    training_dataset = WiderFaceGridDataset(
        args.images,
        args.annotations,
        augment=True,
        min_face_pixels=args.min_face_pixels,
        min_faces_per_image=args.min_faces_per_image,
        max_faces_per_image=args.max_faces_per_image,
        require_detectable_face=True,
        require_all_faces_detectable=args.require_all_faces_detectable,
        clean_full_faces_only=args.clean_full_faces_only,
    )
    validation_dataset = WiderFaceGridDataset(
        args.images,
        args.annotations,
        augment=False,
        min_face_pixels=args.min_face_pixels,
        min_faces_per_image=args.min_faces_per_image,
        max_faces_per_image=args.max_faces_per_image,
        require_detectable_face=True,
        require_all_faces_detectable=args.require_all_faces_detectable,
        clean_full_faces_only=args.clean_full_faces_only,
    )
    indices = list(range(len(training_dataset)))
    random.Random(args.seed).shuffle(indices)
    validation_count = min(max(1, args.validation_samples), len(indices) - 1)
    validation_indices = indices[:validation_count]
    training_indices = indices[validation_count:]
    loader = DataLoader(
        Subset(training_dataset, training_indices),
        batch_size=args.batch_size,
        shuffle=True,
        num_workers=args.workers,
        pin_memory=device.type == "cuda",
    )
    validation_loader = DataLoader(
        Subset(validation_dataset, validation_indices),
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=args.workers,
        pin_memory=device.type == "cuda",
    )
    model = TinyFaceDetector().to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.learning_rate, weight_decay=1e-4)

    print(
        f"device={device} train_samples={len(training_indices)} "
        f"validation_samples={len(validation_indices)} "
        f"parameters={sum(p.numel() for p in model.parameters())}"
    )
    print(f"macs_per_frame={count_macs()}")
    best_validation_loss = float("inf")
    for epoch in range(1, args.epochs + 1):
        model.train()
        total_sum = 0.0
        objectness_sum = 0.0
        box_sum = 0.0
        for images, targets in loader:
            images = images.to(device)
            targets = targets.to(device)
            optimizer.zero_grad(set_to_none=True)
            predictions = model(images)
            total, objectness, box = detection_loss(
                predictions, targets, args.positive_weight
            )
            total.backward()
            optimizer.step()
            total_sum += float(total.detach())
            objectness_sum += float(objectness.detach())
            box_sum += float(box.detach())

        batches = max(1, len(loader))
        validation_loss, precision, recall, f1_score = evaluate(
            model, validation_loader, device, positive_weight=args.positive_weight
        )
        print(
            f"epoch={epoch:03d} train_total={total_sum / batches:.6f} "
            f"objectness={objectness_sum / batches:.6f} box={box_sum / batches:.6f} "
            f"val_total={validation_loss:.6f} precision={precision:.4f} "
            f"recall={recall:.4f} f1={f1_score:.4f}"
        )
        if validation_loss < best_validation_loss:
            best_validation_loss = validation_loss
            save_checkpoint(args.output, model, epoch, validation_loss)
            print(f"BEST_CHECKPOINT epoch={epoch:03d} val_total={validation_loss:.6f}")

    print(f"CHECKPOINT={args.output}")


if __name__ == "__main__":
    main()
