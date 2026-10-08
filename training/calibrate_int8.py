from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as functional
from torch import Tensor, nn
from torch.utils.data import DataLoader

from .export_weights import export_checkpoint, fuse_conv_bn
from .model import TinyFaceDetector
from .yolo_face_dataset import YoloFaceGridDataset


def quantize_multiplier(real_multiplier: float) -> tuple[int, int]:
    """Represent a positive multiplier as Q31 mantissa and a signed base-2 shift."""
    if not math.isfinite(real_multiplier) or real_multiplier <= 0.0:
        raise ValueError(f"invalid multiplier: {real_multiplier}")
    mantissa, exponent = math.frexp(real_multiplier)
    q31 = int(round(mantissa * (1 << 31)))
    if q31 == 1 << 31:
        q31 //= 2
        exponent += 1
    return q31, exponent


def write_int32_mem(path: Path, values: list[int]) -> None:
    path.write_text(
        "".join(f"{int(value) & 0xFFFFFFFF:08X}\n" for value in values),
        encoding="ascii",
    )


def fused_layers(model: TinyFaceDetector) -> list[tuple[str, nn.Conv2d, Tensor, Tensor, bool]]:
    definitions: list[tuple[str, nn.Conv2d, nn.BatchNorm2d | None, bool]] = [
        ("conv1", model.conv1, model.bn1, True),
        ("conv2", model.conv2, model.bn2, True),
        ("conv3", model.conv3, model.bn3, True),
        ("context1_dw", model.context1_dw, model.context1_dw_bn, True),
        ("context1_pw", model.context1_pw, model.context1_pw_bn, True),
        ("context2_dw", model.context2_dw, model.context2_dw_bn, True),
        ("context2_pw", model.context2_pw, model.context2_pw_bn, True),
        ("head", model.head, None, False),
    ]
    result: list[tuple[str, nn.Conv2d, Tensor, Tensor, bool]] = []
    for name, convolution, batch_norm, has_relu in definitions:
        if batch_norm is None:
            weight = convolution.weight.detach().cpu().to(torch.float32)
            bias = convolution.bias.detach().cpu().to(torch.float32)
        else:
            weight64, bias64 = fuse_conv_bn(convolution, batch_norm)
            weight = weight64.to(torch.float32)
            bias = bias64.to(torch.float32)
        result.append((name, convolution, weight, bias, has_relu))
    return result


def calibrate(
    checkpoint_path: Path,
    image_root: Path,
    label_root: Path,
    output_dir: Path,
    batch_size: int,
) -> dict[str, object]:
    base_manifest = export_checkpoint(checkpoint_path, output_dir)
    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=True)
    model = TinyFaceDetector()
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()
    layers = fused_layers(model)

    dataset = YoloFaceGridDataset(
        image_root,
        label_root,
        augment=False,
        min_face_pixels=16,
        min_faces_per_image=1,
        max_faces_per_image=3,
        require_all_faces_detectable=True,
    )
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=False, num_workers=0)
    relu_maxima = {name: 0.0 for name, _, _, _, has_relu in layers if has_relu}
    head_abs_max = torch.zeros(5, dtype=torch.float32)

    with torch.inference_mode():
        for images, _ in loader:
            activations = images
            for name, convolution, weight, bias, has_relu in layers:
                activations = functional.conv2d(
                    activations,
                    weight,
                    bias,
                    stride=convolution.stride,
                    padding=convolution.padding,
                    dilation=convolution.dilation,
                    groups=convolution.groups,
                )
                if has_relu:
                    activations = functional.relu(activations)
                    relu_maxima[name] = max(relu_maxima[name], float(activations.max()))
                else:
                    batch_max = activations.abs().amax(dim=(0, 2, 3)).cpu()
                    head_abs_max = torch.maximum(head_abs_max, batch_max)

    base_layers = {str(layer["name"]): layer for layer in base_manifest["layers"]}
    input_scale = 1.0 / 255.0
    calibrated_layers: list[dict[str, object]] = []
    for name, _, _, _, has_relu in layers:
        base_layer = base_layers[name]
        weight_scales = [float(value) for value in base_layer["weight_scale_per_output"]]
        fused_bias = [float(value) for value in base_layer["fused_bias_float"]]
        accumulator_scales = [input_scale * value for value in weight_scales]
        bias_int32 = [
            int(np.clip(np.rint(bias / scale), -(1 << 31), (1 << 31) - 1))
            for bias, scale in zip(fused_bias, accumulator_scales)
        ]
        write_int32_mem(output_dir / f"{name}_bias.mem", bias_int32)

        entry: dict[str, object] = {
            "name": name,
            "input_scale": input_scale,
            "weight_scale_per_output": weight_scales,
            "accumulator_scale_per_output": accumulator_scales,
            "bias_int32": bias_int32,
            "bias_mem_file": f"{name}_bias.mem",
        }
        if has_relu:
            output_scale = max(relu_maxima[name] / 255.0, 1.0 / (255.0 * 65536.0))
            multipliers = [scale / output_scale for scale in accumulator_scales]
            q31_and_exponent = [quantize_multiplier(value) for value in multipliers]
            multiplier_q31 = [value[0] for value in q31_and_exponent]
            multiplier_exponent = [value[1] for value in q31_and_exponent]
            write_int32_mem(output_dir / f"{name}_multiplier_q31.mem", multiplier_q31)
            (output_dir / f"{name}_multiplier_exponent.mem").write_text(
                "".join(f"{value}\n" for value in multiplier_exponent), encoding="ascii"
            )
            entry.update(
                {
                    "activation": "relu_uint8",
                    "observed_output_max": relu_maxima[name],
                    "output_scale": output_scale,
                    "requant_multiplier_float_per_output": multipliers,
                    "requant_multiplier_q31_per_output": multiplier_q31,
                    "requant_multiplier_exponent_per_output": multiplier_exponent,
                    "multiplier_q31_mem_file": f"{name}_multiplier_q31.mem",
                    "multiplier_exponent_mem_file": f"{name}_multiplier_exponent.mem",
                }
            )
            input_scale = output_scale
        else:
            entry.update(
                {
                    "activation": "int32_logits",
                    "observed_output_abs_max_per_channel": head_abs_max.tolist(),
                    "output_dequant_scale_per_channel": accumulator_scales,
                }
            )
        calibrated_layers.append(entry)

    calibration: dict[str, object] = {
        "format_version": 1,
        "checkpoint": str(checkpoint_path),
        "samples": len(dataset),
        "input_format": "grayscale_uint8",
        "input_scale": 1.0 / 255.0,
        "rounding": "nearest",
        "saturation": "relu_uint8_0_255",
        "layers": calibrated_layers,
        "head_note": "Keep head accumulators as int32; multiply by per-channel scale before sigmoid/box decode.",
    }
    (output_dir / "calibration.json").write_text(
        json.dumps(calibration, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return calibration


def main() -> None:
    parser = argparse.ArgumentParser(description="Calibrate TinyFace uint8 activations for PL inference.")
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("--images", type=Path, required=True)
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("training/outputs/rom_calibrated"))
    parser.add_argument("--batch-size", type=int, default=32)
    args = parser.parse_args()
    result = calibrate(args.checkpoint, args.images, args.labels, args.output, args.batch_size)
    print(f"CALIBRATION_OK samples={result['samples']} layers={len(result['layers'])}")
    print(f"CALIBRATION={args.output / 'calibration.json'}")


if __name__ == "__main__":
    main()
