from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate PS runtime constants from INT8 calibration.")
    parser.add_argument("--calibration", type=Path, required=True)
    parser.add_argument("--threshold", type=float, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not 0.0 < args.threshold < 1.0:
        raise ValueError("threshold must be between 0 and 1")

    calibration = json.loads(args.calibration.read_text(encoding="utf-8"))
    head = next(layer for layer in calibration["layers"] if layer["name"] == "head")
    scales = [float(value) for value in head["output_dequant_scale_per_channel"]]
    if len(scales) != 5:
        raise ValueError(f"expected five head output scales, got {len(scales)}")

    names = ["SCORE", "OFFSET_X", "OFFSET_Y", "BOX_W", "BOX_H"]
    lines = [
        "#pragma once",
        "",
        "/* Generated from calibration.json; do not edit by hand. */",
        f"#define TINY_FACE_SCORE_THRESHOLD {args.threshold:.8g}f",
    ]
    lines.extend(
        f"#define TINY_FACE_HEAD_{name}_SCALE {scale:.17g}f"
        for name, scale in zip(names, scales)
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(lines) + "\n", encoding="ascii")
    print(f"RUNTIME_PARAMS={args.output}")
    print(f"SCORE_THRESHOLD={args.threshold:.8g}")
    print("HEAD_SCALES=" + ",".join(f"{scale:.17g}" for scale in scales))


if __name__ == "__main__":
    main()
