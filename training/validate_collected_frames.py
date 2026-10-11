from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import cv2
import numpy as np


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate AX7021 HDMI capture frames.")
    parser.add_argument("images", type=Path)
    parser.add_argument("--contact-sheet", type=Path, required=True)
    parser.add_argument("--samples", type=int, default=12)
    args = parser.parse_args()

    paths = sorted(
        path
        for path in args.images.iterdir()
        if path.suffix.lower() in {".png", ".jpg", ".jpeg"}
    )
    if not paths:
        raise SystemExit(f"no images in {args.images}")

    dimensions: set[tuple[int, int]] = set()
    hashes: dict[str, list[str]] = {}
    failed: list[str] = []
    suspicious: list[tuple[str, int, float]] = []
    means: list[float] = []

    for path in paths:
        image = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if image is None:
            failed.append(path.name)
            continue
        height, width = image.shape[:2]
        dimensions.add((width, height))
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        hashes.setdefault(digest, []).append(path.name)
        means.append(float(image.mean()))

        # Broken capture frames previously contained many abrupt horizontal
        # scan-line discontinuities. Count only very strong full-row changes;
        # ordinary object edges do not normally affect most pixels in a row.
        row_delta = np.abs(image[1:].astype(np.int16) - image[:-1].astype(np.int16)).mean(
            axis=(1, 2)
        )
        strong_rows = int(np.count_nonzero(row_delta > 40.0))
        p99 = float(np.percentile(row_delta, 99.0))
        if strong_rows >= 5 or p99 > 45.0:
            suspicious.append((path.name, strong_rows, p99))

    duplicate_groups = [names for names in hashes.values() if len(names) > 1]
    sample_indices = np.linspace(0, len(paths) - 1, min(args.samples, len(paths))).astype(int)
    tiles: list[np.ndarray] = []
    for index in sample_indices:
        image = cv2.imread(str(paths[int(index)]), cv2.IMREAD_COLOR)
        if image is None:
            continue
        tile = cv2.resize(image, (320, 180), interpolation=cv2.INTER_AREA)
        cv2.putText(
            tile,
            paths[int(index)].name[:24],
            (8, 170),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.42,
            (0, 255, 0),
            1,
            cv2.LINE_AA,
        )
        tiles.append(tile)

    while len(tiles) % 4:
        tiles.append(np.zeros((180, 320, 3), dtype=np.uint8))
    rows = [np.hstack(tiles[index : index + 4]) for index in range(0, len(tiles), 4)]
    contact_sheet = np.vstack(rows)
    args.contact_sheet.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(args.contact_sheet), contact_sheet):
        raise RuntimeError(f"failed to write {args.contact_sheet}")

    print(f"FILES={len(paths)}")
    print(f"DECODE_FAILED={len(failed)}")
    print(f"DIMENSIONS={sorted(dimensions)}")
    print(f"EXACT_DUPLICATE_GROUPS={len(duplicate_groups)}")
    print(f"MEAN_BRIGHTNESS_MIN={min(means):.2f}")
    print(f"MEAN_BRIGHTNESS_MAX={max(means):.2f}")
    print(f"HORIZONTAL_BREAK_SUSPECTS={len(suspicious)}")
    for name, count, p99 in suspicious[:20]:
        print(f"SUSPECT={name} strong_rows={count} p99={p99:.2f}")
    print(f"CONTACT_SHEET={args.contact_sheet}")


if __name__ == "__main__":
    main()
