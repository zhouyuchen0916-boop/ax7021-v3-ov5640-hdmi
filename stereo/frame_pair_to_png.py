from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image


WIDTH = 1280
HEIGHT = 720
FRAME_BYTES = WIDTH * HEIGHT * 3


def convert(raw_path: Path, png_path: Path) -> None:
    raw = raw_path.read_bytes()
    if len(raw) != FRAME_BYTES:
        raise ValueError(f"{raw_path}: expected {FRAME_BYTES} bytes, got {len(raw)}")

    # AX7021 DDR stores the current RGB888 stream in B, G, R byte order.
    encoded = Image.frombytes("RGB", (WIDTH, HEIGHT), raw)
    red, green, blue = encoded.split()
    image = Image.merge("RGB", (blue, green, red))
    png_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(png_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert one AX7021 stereo DDR pair to PNG files.")
    parser.add_argument("--root", type=Path, default=Path("stereo/pairs"))
    parser.add_argument("--name", required=True)
    parser.add_argument("--keep-raw", action="store_true")
    args = parser.parse_args()

    left_raw = args.root / "raw" / f"{args.name}_left.bin"
    right_raw = args.root / "raw" / f"{args.name}_right.bin"
    left_png = args.root / "left" / f"{args.name}.png"
    right_png = args.root / "right" / f"{args.name}.png"

    convert(left_raw, left_png)
    convert(right_raw, right_png)
    if not args.keep_raw:
        left_raw.unlink()
        right_raw.unlink()

    print(f"PAIR_CONVERT_OK={args.name}")
    print(f"LEFT={left_png}")
    print(f"RIGHT={right_png}")


if __name__ == "__main__":
    main()
