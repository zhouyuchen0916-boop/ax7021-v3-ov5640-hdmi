from __future__ import annotations

import argparse
from pathlib import Path

import cv2

from calibrate_stereo import detect_corners


def inspect(path: Path, pattern: tuple[int, int]) -> tuple[bool, float, int]:
    image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if image is None:
        return False, 0.0, 0
    corners = detect_corners(image, pattern)
    return corners is not None, float(image.mean()), 0 if corners is None else len(corners)


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate one captured stereo checkerboard pair.")
    parser.add_argument("--left", type=Path, required=True)
    parser.add_argument("--right", type=Path, required=True)
    parser.add_argument("--cols", type=int, default=9)
    parser.add_argument("--rows", type=int, default=6)
    args = parser.parse_args()

    pattern = (args.cols, args.rows)
    left_ok, left_mean, left_count = inspect(args.left, pattern)
    right_ok, right_mean, right_count = inspect(args.right, pattern)
    print(
        f"LEFT={'OK' if left_ok else 'FAIL'} corners={left_count} "
        f"mean={left_mean:.2f} file={args.left}"
    )
    print(
        f"RIGHT={'OK' if right_ok else 'FAIL'} corners={right_count} "
        f"mean={right_mean:.2f} file={args.right}"
    )
    if left_ok and right_ok:
        print("PAIR_VALID=1")
        return
    print("PAIR_VALID=0")
    raise SystemExit(2)


if __name__ == "__main__":
    main()
