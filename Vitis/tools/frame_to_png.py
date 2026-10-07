from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageOps, ImageStat


WIDTH = 1280
HEIGHT = 720
FRAME_BYTES = WIDTH * HEIGHT * 3


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert an AX7021 RGB888 DDR dump to PNG previews.")
    parser.add_argument("input", type=Path)
    args = parser.parse_args()

    raw = args.input.read_bytes()
    if len(raw) != FRAME_BYTES:
        raise SystemExit(f"expected {FRAME_BYTES} bytes, got {len(raw)}")

    output_dir = args.input.parent
    rgb = Image.frombytes("RGB", (WIDTH, HEIGHT), raw)
    red, green, blue = rgb.split()
    bgr = Image.merge("RGB", (blue, green, red))
    gray = ImageOps.grayscale(rgb)
    gray_160 = gray.resize((160, 120), Image.Resampling.BILINEAR)

    rgb.save(output_dir / "frame_rgb.png")
    bgr.save(output_dir / "frame_bgr.png")
    gray_160.save(output_dir / "frame_gray_160x120.png")

    mean_rgb = ImageStat.Stat(rgb).mean
    print(f"FRAME_CONVERT_OK bytes={len(raw)}")
    print("RGB_MEAN=" + ",".join(f"{value:.2f}" for value in mean_rgb))
    print(f"RGB={output_dir / 'frame_rgb.png'}")
    print(f"BGR={output_dir / 'frame_bgr.png'}")
    print(f"GRAY160={output_dir / 'frame_gray_160x120.png'}")


if __name__ == "__main__":
    main()
