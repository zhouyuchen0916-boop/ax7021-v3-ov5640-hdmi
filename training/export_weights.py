from __future__ import annotations

import argparse
import json
import zlib
from pathlib import Path

import numpy as np
import torch
from torch import Tensor, nn

from .model import TinyFaceDetector, count_macs


def fuse_conv_bn(conv: nn.Conv2d, batch_norm: nn.BatchNorm2d) -> tuple[Tensor, Tensor]:
    weight = conv.weight.detach().cpu().to(torch.float64)
    bias = torch.zeros(conv.out_channels, dtype=torch.float64)
    gamma = batch_norm.weight.detach().cpu().to(torch.float64)
    beta = batch_norm.bias.detach().cpu().to(torch.float64)
    mean = batch_norm.running_mean.detach().cpu().to(torch.float64)
    variance = batch_norm.running_var.detach().cpu().to(torch.float64)
    factor = gamma / torch.sqrt(variance + batch_norm.eps)
    return weight * factor[:, None, None, None], (bias - mean) * factor + beta


def quantize_per_output_channel(weight: Tensor) -> tuple[np.ndarray, np.ndarray]:
    flat = weight.numpy().reshape(weight.shape[0], -1)
    maximum = np.max(np.abs(flat), axis=1)
    scales = np.where(maximum > 0.0, maximum / 127.0, 1.0 / 127.0)
    quantized = np.rint(flat / scales[:, None]).clip(-127, 127).astype(np.int8)
    return quantized.reshape(tuple(weight.shape)), scales.astype(np.float32)


def write_mem(path: Path, values: np.ndarray) -> None:
    unsigned = values.reshape(-1).view(np.uint8)
    path.write_text("".join(f"{int(value):02X}\n" for value in unsigned), encoding="ascii")


def export_checkpoint(checkpoint_path: Path, output_dir: Path) -> dict[str, object]:
    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=True)
    model = TinyFaceDetector()
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()
    output_dir.mkdir(parents=True, exist_ok=True)

    layers: list[tuple[str, nn.Conv2d, nn.BatchNorm2d | None]] = [
        ("conv1", model.conv1, model.bn1),
        ("conv2", model.conv2, model.bn2),
        ("conv3", model.conv3, model.bn3),
        ("head", model.head, None),
    ]
    manifest_layers: list[dict[str, object]] = []
    for name, convolution, batch_norm in layers:
        if batch_norm is None:
            fused_weight = convolution.weight.detach().cpu().to(torch.float64)
            fused_bias = convolution.bias.detach().cpu().to(torch.float64)
        else:
            fused_weight, fused_bias = fuse_conv_bn(convolution, batch_norm)
        quantized_weight, weight_scales = quantize_per_output_channel(fused_weight)
        mem_path = output_dir / f"{name}_weights.mem"
        write_mem(mem_path, quantized_weight)
        raw_bytes = quantized_weight.reshape(-1).view(np.uint8).tobytes()
        manifest_layers.append(
            {
                "name": name,
                "weight_shape_oihw": list(quantized_weight.shape),
                "weight_count": int(quantized_weight.size),
                "weight_order": "OIHW",
                "weight_format": "signed_int8_twos_complement_hex",
                "weight_scale_per_output": weight_scales.tolist(),
                "fused_bias_float": fused_bias.numpy().astype(np.float32).tolist(),
                "crc32": f"{zlib.crc32(raw_bytes) & 0xFFFFFFFF:08X}",
                "mem_file": mem_path.name,
            }
        )

    manifest: dict[str, object] = {
        "format_version": 1,
        "model": "TinyFaceDetector",
        "trained_epochs": int(checkpoint.get("trained_epochs", 0)),
        "input_shape_nchw": [1, 1, 120, 160],
        "output_shape_nchw": [1, 5, 15, 20],
        "macs_per_frame": count_macs(),
        "layers": manifest_layers,
        "note": "Bias and requantization become fixed-point after activation calibration.",
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Fuse BN and export INT8 weights for PL ROMs.")
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("--output", type=Path, default=Path("training/outputs/rom"))
    args = parser.parse_args()
    manifest = export_checkpoint(args.checkpoint, args.output)
    total_weights = sum(int(layer["weight_count"]) for layer in manifest["layers"])
    print(f"WEIGHT_EXPORT_OK layers={len(manifest['layers'])} int8_weights={total_weights}")
    print(f"MANIFEST={args.output / 'manifest.json'}")


if __name__ == "__main__":
    main()
