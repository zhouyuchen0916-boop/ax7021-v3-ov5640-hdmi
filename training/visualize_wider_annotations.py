from __future__ import annotations

import argparse
import math
from pathlib import Path

from PIL import Image, ImageDraw

from .widerface_dataset import parse_widerface_annotations


def main() -> None:
    parser = argparse.ArgumentParser(description="Render WIDER-style face boxes for QA.")
    parser.add_argument("--images", type=Path, required=True)
    parser.add_argument("--annotations", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--columns", type=int, default=4)
    parser.add_argument("--samples", type=int, default=0, help="0 renders every sample")
    args = parser.parse_args()

    samples = parse_widerface_annotations(args.annotations)
    if args.samples > 0 and args.samples < len(samples):
        count = args.samples
        indices = [round(i * (len(samples) - 1) / max(1, count - 1)) for i in range(count)]
        samples = [samples[index] for index in indices]
    tile_width, tile_height = 320, 180
    rows = math.ceil(len(samples) / args.columns)
    sheet = Image.new("RGB", (args.columns * tile_width, rows * tile_height), "black")

    for index, sample in enumerate(samples):
        with Image.open(args.images / sample.relative_path) as source:
            source = source.convert("RGB")
            source_width, source_height = source.size
            tile = source.resize((tile_width, tile_height), Image.Resampling.BILINEAR)
        draw = ImageDraw.Draw(tile)
        for annotation in sample.annotations:
            x, y, width, height = annotation.box_xywh
            draw.rectangle(
                (
                    round(x * tile_width / source_width),
                    round(y * tile_height / source_height),
                    round((x + width) * tile_width / source_width),
                    round((y + height) * tile_height / source_height),
                ),
                outline="#00ff40",
                width=2,
            )
        draw.rectangle((0, tile_height - 16, tile_width, tile_height), fill="black")
        draw.text(
            (4, tile_height - 14),
            f"{sample.relative_path[:34]} faces={len(sample.annotations)}",
            fill="#00ff40",
        )
        sheet.paste(
            tile,
            ((index % args.columns) * tile_width, (index // args.columns) * tile_height),
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(args.output, quality=92)
    print(f"SAMPLES={len(samples)}")
    print(f"OUTPUT={args.output}")


if __name__ == "__main__":
    main()
