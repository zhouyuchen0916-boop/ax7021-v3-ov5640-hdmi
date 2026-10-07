from __future__ import annotations

import argparse
import random
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as functional
from torch import Tensor
from torch.utils.data import DataLoader

from .model import TinyFaceDetector, count_macs
from .widerface_dataset import WiderFaceGridDataset


def detection_loss(prediction: Tensor, target: Tensor) -> tuple[Tensor, Tensor, Tensor]:
    positive = target[:, 0] > 0.5
    objectness_loss = functional.binary_cross_entropy_with_logits(
        prediction[:, 0], target[:, 0], pos_weight=prediction.new_tensor(8.0)
    )
    if positive.any():
        predicted_boxes = prediction[:, 1:5].sigmoid().permute(0, 2, 3, 1)[positive]
        target_boxes = target[:, 1:5].permute(0, 2, 3, 1)[positive]
        box_loss = functional.smooth_l1_loss(predicted_boxes, target_boxes)
    else:
        box_loss = prediction.sum() * 0.0
    total = objectness_loss + 5.0 * box_loss
    return total, objectness_loss, box_loss


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
    args = parser.parse_args()

    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    dataset = WiderFaceGridDataset(args.images, args.annotations)
    loader = DataLoader(
        dataset,
        batch_size=args.batch_size,
        shuffle=True,
        num_workers=args.workers,
        pin_memory=device.type == "cuda",
    )
    model = TinyFaceDetector().to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.learning_rate, weight_decay=1e-4)

    print(f"device={device} samples={len(dataset)} parameters={sum(p.numel() for p in model.parameters())}")
    print(f"macs_per_frame={count_macs()}")
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
            total, objectness, box = detection_loss(predictions, targets)
            total.backward()
            optimizer.step()
            total_sum += float(total.detach())
            objectness_sum += float(objectness.detach())
            box_sum += float(box.detach())

        batches = max(1, len(loader))
        print(
            f"epoch={epoch:03d} total={total_sum / batches:.6f} "
            f"objectness={objectness_sum / batches:.6f} box={box_sum / batches:.6f}"
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "model_state_dict": model.cpu().state_dict(),
            "input_shape": [1, 1, 120, 160],
            "output_shape": [1, 5, 15, 20],
            "trained_epochs": args.epochs,
        },
        args.output,
    )
    print(f"CHECKPOINT={args.output}")


if __name__ == "__main__":
    main()
