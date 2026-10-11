from __future__ import annotations

import argparse
from pathlib import Path

from .widerface_dataset import parse_widerface_annotations


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg"}


def image_names(directory: Path) -> set[str]:
    return {
        path.name
        for path in directory.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Combine manually labelled field faces with zero-face hard negatives."
    )
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--positive-images", type=Path, required=True)
    parser.add_argument("--positive-annotations", type=Path, required=True)
    parser.add_argument("--negative-images", type=Path, required=True)
    parser.add_argument("--rejected", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--negative-output",
        type=Path,
        help="Optionally write a second annotation file containing only zero-face images.",
    )
    args = parser.parse_args()

    root = args.root.resolve()
    positive_images = args.positive_images.resolve()
    negative_images = args.negative_images.resolve()
    positive_samples = parse_widerface_annotations(args.positive_annotations)
    annotated_names = {sample.relative_path for sample in positive_samples}
    available_positive_names = image_names(positive_images)
    missing = sorted(annotated_names - available_positive_names)
    if missing:
        raise ValueError(f"annotation references missing positive images: {missing[:10]}")

    rejected: set[str] = set()
    if args.rejected is not None and args.rejected.exists():
        rejected = {
            line.strip()
            for line in args.rejected.read_text(encoding="utf-8").splitlines()
            if line.strip()
        }
    unprocessed = sorted(available_positive_names - annotated_names - rejected)
    if unprocessed:
        raise ValueError(
            f"{len(unprocessed)} positive images are not annotated or rejected; "
            f"first={unprocessed[:5]}"
        )

    lines: list[str] = []
    face_count = 0
    for sample in positive_samples:
        relative = (positive_images / sample.relative_path).relative_to(root).as_posix()
        lines.extend([relative, str(len(sample.annotations))])
        for annotation in sample.annotations:
            x, y, width, height = annotation.box_xywh
            lines.append(
                f"{x:g} {y:g} {width:g} {height:g} "
                f"{annotation.blur} {annotation.expression} {annotation.illumination} "
                f"{annotation.invalid} {annotation.occlusion} {annotation.pose}"
            )
            face_count += 1

    negative_paths = sorted(
        path
        for path in negative_images.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
    )
    for path in negative_paths:
        lines.extend([path.relative_to(root).as_posix(), "0"])

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    if args.negative_output is not None:
        negative_lines: list[str] = []
        for path in negative_paths:
            negative_lines.extend([path.relative_to(root).as_posix(), "0"])
        args.negative_output.parent.mkdir(parents=True, exist_ok=True)
        args.negative_output.write_text(
            "\n".join(negative_lines) + ("\n" if negative_lines else ""),
            encoding="utf-8",
        )
    print(f"POSITIVE_IMAGES={len(positive_samples)}")
    print(f"ANNOTATED_FACES={face_count}")
    print(f"REJECTED_POSITIVE_IMAGES={len(rejected)}")
    print(f"NEGATIVE_IMAGES={len(negative_paths)}")
    print(f"OUTPUT={args.output}")
    if args.negative_output is not None:
        print(f"NEGATIVE_OUTPUT={args.negative_output}")


if __name__ == "__main__":
    main()
