from __future__ import annotations

import argparse
import json
from pathlib import Path


def c_float(value: float) -> str:
    text = f"{float(value):.9g}"
    if "." not in text and "e" not in text.lower():
        text += ".0"
    return text + "f"


def c_array(name: str, values: list[float]) -> list[str]:
    formatted = ", ".join(c_float(value) for value in values)
    return [f"static const float {name}[{len(values)}] = {{", f"    {formatted}", "};"]


def flatten(matrix: list) -> list[float]:
    result: list[float] = []
    for row in matrix:
        if isinstance(row, list):
            result.extend(float(value) for value in row)
        else:
            result.append(float(row))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate AX7021 stereo calibration C constants.")
    parser.add_argument("--calibration", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    data = json.loads(args.calibration.read_text(encoding="utf-8"))
    lines = [
        "#ifndef STEREO_CALIBRATION_PARAMS_H_",
        "#define STEREO_CALIBRATION_PARAMS_H_",
        "",
        "/* Generated from stereo/output/stereo_calibration.json. */",
        f"#define STEREO_RECTIFIED_FOCAL_PX {c_float(data['projection_left'][0][0])}",
        f"#define STEREO_BASELINE_MM {c_float(data['baseline_mm'])}",
        "",
    ]
    lines += c_array("STEREO_CAMERA1_K", flatten(data["left_camera_matrix"]))
    lines += c_array("STEREO_CAMERA1_D", flatten(data["left_distortion"]))
    lines += c_array("STEREO_CAMERA1_R", flatten(data["rectification_left"]))
    lines += c_array("STEREO_CAMERA2_K", flatten(data["right_camera_matrix"]))
    lines += c_array("STEREO_CAMERA2_D", flatten(data["right_distortion"]))
    lines += c_array("STEREO_CAMERA2_R", flatten(data["rectification_right"]))
    lines += [
        f"#define STEREO_RECTIFIED_CX {c_float(data['projection_left'][0][2])}",
        f"#define STEREO_RECTIFIED_CY {c_float(data['projection_left'][1][2])}",
        "",
        "#endif /* STEREO_CALIBRATION_PARAMS_H_ */",
        "",
    ]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(lines), encoding="ascii")
    print(f"STEREO_RUNTIME_PARAMS_OK={args.output}")


if __name__ == "__main__":
    main()
