from __future__ import annotations

import argparse
from pathlib import Path

import torch
from PIL import Image, ImageDraw

from .model import INPUT_HEIGHT, INPUT_WIDTH, TinyFaceDetector, decode_predictions, non_max_suppression
from .yolo_face_dataset import YoloFaceGridDataset


def draw_box(
    draw: ImageDraw.ImageDraw,
    box: tuple[float, float, float, float, float],
    width: int,
    height: int,
    color: str,
    label: str,
) -> None:
    left, top, right, bottom, _ = box
    coordinates = (
        round(left * width),
        round(top * height),
        round(right * width),
        round(bottom * height),
    )
    draw.rectangle(coordinates, outline=color, width=3)
    draw.text((coordinates[0] + 3, coordinates[1] + 3), label, fill=color)


def main() -> None:
    parser = argparse.ArgumentParser(description="Render YOLO ground truth and TinyFace predictions.")
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("--images", type=Path, required=True)
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument("--threshold", type=float, default=0.92)
    parser.add_argument("--count", type=int, default=12)
    parser.add_argument("--columns", type=int, default=4)
    parser.add_argument("--output", type=Path, required=True)
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
    checkpoint = torch.load(args.checkpoint, map_location="cpu", weights_only=True)
    model = TinyFaceDetector()
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()

    count = min(max(1, args.count), len(dataset))
    indices = [round(index * (len(dataset) - 1) / max(1, count - 1)) for index in range(count)]
    tile_width, tile_height = 320, 264
    rows = (count + args.columns - 1) // args.columns
    sheet = Image.new("RGB", (args.columns * tile_width, rows * tile_height), "white")

    with torch.inference_mode():
        for tile_index, dataset_index in enumerate(indices):
            image_tensor, _ = dataset[dataset_index]
            raw_prediction = model(image_tensor.unsqueeze(0))
            decoded = decode_predictions(raw_prediction, args.threshold)[0]
            predicted = non_max_suppression(decoded, iou_threshold=0.35, max_detections=10)

            sample = dataset.samples[dataset_index]
            with Image.open(sample.image_path) as source:
                tile = source.convert("RGB").resize((tile_width, 240), Image.Resampling.BILINEAR)
            draw = ImageDraw.Draw(tile)
            for center_x, center_y, width, height in sample.boxes_cxcywh:
                target = (
                    center_x - width / 2.0,
                    center_y - height / 2.0,
                    center_x + width / 2.0,
                    center_y + height / 2.0,
                    1.0,
                )
                draw_box(draw, target, tile_width, 240, "#00ff00", "GT")
            for box in predicted:
                draw_box(draw, box, tile_width, 240, "#ff3030", f"P {box[4]:.2f}")

            canvas = Image.new("RGB", (tile_width, tile_height), "white")
            canvas.paste(tile, (0, 0))
            ImageDraw.Draw(canvas).text(
                (4, 244),
                f"sample={dataset_index} gt={len(sample.boxes_cxcywh)} pred={len(predicted)}",
                fill="black",
            )
            sheet.paste(
                canvas,
                ((tile_index % args.columns) * tile_width, (tile_index // args.columns) * tile_height),
            )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(args.output)
    print(f"PREVIEW={args.output}")
    print(f"INPUT={INPUT_WIDTH}x{INPUT_HEIGHT} threshold={args.threshold:.2f} samples={count}")


if __name__ == "__main__":
    main()
