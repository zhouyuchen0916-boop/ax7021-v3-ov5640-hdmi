from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image


LAYER_DEFINITIONS = [
    ("conv1", 1, 8, 3, 2, 1, 1, 1, 120, 160),
    ("conv2", 8, 16, 3, 2, 1, 1, 1, 60, 80),
    ("conv3", 16, 24, 3, 2, 1, 1, 1, 30, 40),
    ("context1_dw", 24, 24, 3, 1, 2, 2, 24, 15, 20),
    ("context1_pw", 24, 24, 1, 1, 0, 1, 1, 15, 20),
    ("context2_dw", 24, 24, 3, 1, 4, 4, 24, 15, 20),
    ("context2_pw", 24, 24, 1, 1, 0, 1, 1, 15, 20),
    ("head", 24, 5, 1, 1, 0, 1, 1, 15, 20),
]


def read_signed_mem(path: Path, bits: int) -> np.ndarray:
    values = np.array([int(line, 16) for line in path.read_text().splitlines()], dtype=np.int64)
    sign = 1 << (bits - 1)
    return np.where(values & sign, values - (1 << bits), values)


def read_decimal_mem(path: Path) -> np.ndarray:
    return np.array([int(line) for line in path.read_text().splitlines()], dtype=np.int64)


def requantize(accumulator: np.ndarray, q31: np.ndarray, exponent: np.ndarray) -> np.ndarray:
    result = np.empty_like(accumulator, dtype=np.int64)
    for channel in range(accumulator.shape[0]):
        product = accumulator[channel].astype(np.int64) * int(q31[channel])
        shift = 31 - int(exponent[channel])
        absolute = np.abs(product)
        if shift > 0:
            rounded = (absolute + (1 << (shift - 1))) >> shift
        else:
            rounded = absolute << (-shift)
        result[channel] = np.where(product < 0, -rounded, rounded)
    return np.clip(result, 0, 255).astype(np.uint8)


def convolve(
    source: np.ndarray,
    weights: np.ndarray,
    bias: np.ndarray,
    stride: int,
    padding: int,
    dilation: int,
    groups: int,
) -> np.ndarray:
    input_channels, input_height, input_width = source.shape
    output_channels, channels_per_group, kernel, _ = weights.shape
    output_height = (input_height + 2 * padding - dilation * (kernel - 1) - 1) // stride + 1
    output_width = (input_width + 2 * padding - dilation * (kernel - 1) - 1) // stride + 1
    padded = np.pad(source.astype(np.int32), ((0, 0), (padding, padding), (padding, padding)))
    output = np.empty((output_channels, output_height, output_width), dtype=np.int64)
    outputs_per_group = output_channels // groups
    for output_channel in range(output_channels):
        group = output_channel // outputs_per_group
        input_start = group * (input_channels // groups)
        for output_y in range(output_height):
            input_y = output_y * stride
            for output_x in range(output_width):
                input_x = output_x * stride
                patch = padded[
                    input_start : input_start + channels_per_group,
                    input_y : input_y + dilation * (kernel - 1) + 1 : dilation,
                    input_x : input_x + dilation * (kernel - 1) + 1 : dilation,
                ]
                output[output_channel, output_y, output_x] = (
                    int(bias[output_channel])
                    + int(np.sum(patch.astype(np.int64) * weights[output_channel].astype(np.int64)))
                )
    return output


def format_array(type_name: str, name: str, values: np.ndarray, columns: int = 16) -> str:
    flat = values.reshape(-1)
    lines = []
    for start in range(0, flat.size, columns):
        lines.append("    " + ", ".join(str(int(value)) for value in flat[start : start + columns]))
    return f"static const {type_name} {name}[{flat.size}] = {{\n" + ",\n".join(lines) + "\n};\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate HLS ROM headers and an exact C-sim vector.")
    parser.add_argument("--calibrated", type=Path, required=True)
    parser.add_argument("--test-image", type=Path, required=True)
    parser.add_argument("--source-output", type=Path, required=True)
    parser.add_argument("--test-output", type=Path, required=True)
    args = parser.parse_args()

    calibration = json.loads((args.calibrated / "calibration.json").read_text(encoding="utf-8"))
    calibration_layers = {layer["name"]: layer for layer in calibration["layers"]}
    source_parts = ["#pragma once\n", "#include <stdint.h>\n"]

    with Image.open(args.test_image) as image:
        resized = image.convert("L").resize((160, 120), Image.Resampling.BILINEAR)
        activations = np.asarray(resized, dtype=np.uint8)[None, :, :]
    test_input = activations.copy()

    for (
        name,
        input_channels,
        output_channels,
        kernel,
        stride,
        padding,
        dilation,
        groups,
        _,
        _,
    ) in LAYER_DEFINITIONS:
        channels_per_group = input_channels // groups
        weights = read_signed_mem(args.calibrated / f"{name}_weights.mem", 8).reshape(
            output_channels, channels_per_group, kernel, kernel
        )
        bias = read_signed_mem(args.calibrated / f"{name}_bias.mem", 32)
        source_parts.append(format_array("int8_t", f"{name}_weights", weights))
        source_parts.append(format_array("int32_t", f"{name}_bias", bias))
        accumulator = convolve(activations, weights, bias, stride, padding, dilation, groups)
        if name != "head":
            q31 = read_signed_mem(args.calibrated / f"{name}_multiplier_q31.mem", 32)
            exponent = read_decimal_mem(args.calibrated / f"{name}_multiplier_exponent.mem")
            source_parts.append(format_array("int32_t", f"{name}_multiplier_q31", q31))
            source_parts.append(format_array("int8_t", f"{name}_multiplier_exponent", exponent))
            activations = requantize(accumulator, q31, exponent)
        else:
            activations = accumulator.astype(np.int32)

    args.source_output.parent.mkdir(parents=True, exist_ok=True)
    args.source_output.write_text("\n".join(source_parts), encoding="ascii")
    args.test_output.parent.mkdir(parents=True, exist_ok=True)
    args.test_output.write_text(
        "#pragma once\n#include <stdint.h>\n\n"
        + format_array("uint8_t", "test_input", test_input)
        + "\n"
        + format_array("int32_t", "expected_output", activations),
        encoding="ascii",
    )
    print(f"PARAMETERS={args.source_output}")
    print(f"TEST_VECTOR={args.test_output}")
    print(f"EXPECTED_MIN={int(activations.min())} EXPECTED_MAX={int(activations.max())}")


if __name__ == "__main__":
    main()
