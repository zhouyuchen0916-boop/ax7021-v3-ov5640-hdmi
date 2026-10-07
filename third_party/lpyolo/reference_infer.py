from __future__ import annotations

import argparse
import time
from pathlib import Path
import sys

SCRIPT_DIR = Path(__file__).resolve().parent
LOCAL_DEPS = SCRIPT_DIR / "python_deps"
if LOCAL_DEPS.exists():
    sys.path.insert(0, str(LOCAL_DEPS))

import cv2
import numpy as np
import onnx
import torch
import torch.nn.functional as functional
from onnx import numpy_helper


MODEL_PATH = SCRIPT_DIR / "model_4w4a" / "4w4a" / "best.finn.onnx"
INPUT_SIZE = 416
STRIDE = 32.0
ANCHORS = np.asarray(((10.0, 14.0), (23.0, 27.0), (37.0, 58.0)))


def _attributes(node: onnx.NodeProto) -> dict[str, object]:
    return {
        attribute.name: onnx.helper.get_attribute_value(attribute)
        for attribute in node.attribute
    }


def _tensor(value: np.ndarray) -> torch.Tensor:
    return torch.from_numpy(np.asarray(value, dtype=np.float32).copy())


def _multithreshold(values: torch.Tensor, thresholds: torch.Tensor) -> torch.Tensor:
    if thresholds.ndim != 2 or thresholds.shape[0] not in (1, values.shape[1]):
        raise ValueError(
            f"unsupported MultiThreshold shapes: input={tuple(values.shape)}, "
            f"thresholds={tuple(thresholds.shape)}"
        )
    if thresholds.shape[0] == 1:
        thresholds = thresholds.expand(values.shape[1], -1)
    result = torch.empty_like(values)
    for channel in range(values.shape[1]):
        channel_values = values[:, channel : channel + 1]
        channel_thresholds = thresholds[channel].reshape(1, -1, 1, 1)
        result[:, channel : channel + 1] = (
            channel_values.unsqueeze(2) >= channel_thresholds.unsqueeze(1)
        ).sum(dim=2, dtype=torch.float32)
    return result


class FinnOnnxReference:
    def __init__(self, model_path: Path) -> None:
        self.model = onnx.load(model_path)
        self.initializers = {
            item.name: _tensor(numpy_helper.to_array(item))
            for item in self.model.graph.initializer
        }

    def __call__(self, image_nchw: torch.Tensor) -> torch.Tensor:
        context = dict(self.initializers)
        context[self.model.graph.input[0].name] = image_nchw.float()

        with torch.inference_mode():
            for node in self.model.graph.node:
                inputs = [context[name] for name in node.input]
                attributes = _attributes(node)

                if node.op_type == "Conv":
                    pads = attributes.get("pads", [0, 0, 0, 0])
                    if pads[0] != pads[2] or pads[1] != pads[3]:
                        raise ValueError(f"asymmetric Conv padding is unsupported: {pads}")
                    output = functional.conv2d(
                        inputs[0],
                        inputs[1],
                        bias=inputs[2] if len(inputs) > 2 else None,
                        stride=tuple(attributes.get("strides", [1, 1])),
                        padding=(pads[0], pads[1]),
                        dilation=tuple(attributes.get("dilations", [1, 1])),
                        groups=int(attributes.get("group", 1)),
                    )
                elif node.op_type == "Mul":
                    output = inputs[0] * inputs[1]
                elif node.op_type == "Div":
                    output = inputs[0] / inputs[1]
                elif node.op_type == "Add":
                    output = inputs[0] + inputs[1]
                elif node.op_type == "BatchNormalization":
                    output = functional.batch_norm(
                        inputs[0],
                        inputs[3],
                        inputs[4],
                        inputs[1],
                        inputs[2],
                        training=False,
                        momentum=float(attributes.get("momentum", 0.9)),
                        eps=float(attributes.get("epsilon", 1e-5)),
                    )
                elif node.op_type == "MaxPool":
                    pads = attributes.get("pads", [0, 0, 0, 0])
                    output = functional.max_pool2d(
                        inputs[0],
                        kernel_size=tuple(attributes["kernel_shape"]),
                        stride=tuple(attributes.get("strides", attributes["kernel_shape"])),
                        padding=(pads[0], pads[1]),
                    )
                elif node.op_type == "MultiThreshold":
                    output = _multithreshold(inputs[0], inputs[1])
                    output = output * float(attributes.get("out_scale", 1.0))
                    output = output + float(attributes.get("out_bias", 0.0))
                else:
                    raise ValueError(
                        f"unsupported node {node.name}: {node.domain}:{node.op_type}"
                    )

                if len(node.output) != 1:
                    raise ValueError(f"multiple outputs are unsupported: {node.name}")
                context[node.output[0]] = output

        return context[self.model.graph.output[0].name]


def letterbox(image: np.ndarray) -> tuple[np.ndarray, float, tuple[float, float]]:
    height, width = image.shape[:2]
    ratio = min(INPUT_SIZE / height, INPUT_SIZE / width)
    resized_width = round(width * ratio)
    resized_height = round(height * ratio)
    pad_x = (INPUT_SIZE - resized_width) / 2.0
    pad_y = (INPUT_SIZE - resized_height) / 2.0
    resized = cv2.resize(image, (resized_width, resized_height), interpolation=cv2.INTER_LINEAR)
    top = round(pad_y - 0.1)
    bottom = round(pad_y + 0.1)
    left = round(pad_x - 0.1)
    right = round(pad_x + 0.1)
    padded = cv2.copyMakeBorder(
        resized, top, bottom, left, right, cv2.BORDER_CONSTANT, value=(114, 114, 114)
    )
    return padded, ratio, (pad_x, pad_y)


def decode(output: torch.Tensor, confidence: float) -> list[tuple[float, ...]]:
    values = output.reshape(1, 3, 6, 13, 13).permute(0, 1, 3, 4, 2)[0].cpu().numpy()
    grid_y, grid_x = np.meshgrid(np.arange(13), np.arange(13), indexing="ij")
    grid = np.stack((grid_x, grid_y), axis=-1)[None, ...]
    xy = (values[..., 0:2] + 0.5 + grid) * STRIDE
    wh = (values[..., 2:4] + 1.0) ** 2 * ANCHORS[:, None, None, :]
    objectness = values[..., 4] / 2.0 + 0.5
    class_score = values[..., 5] / 2.0 + 0.5
    scores = objectness * class_score

    detections: list[tuple[float, ...]] = []
    for anchor, row, column in np.argwhere(scores >= confidence):
        center_x, center_y = xy[anchor, row, column]
        box_width, box_height = wh[anchor, row, column]
        detections.append(
            (
                float(center_x - box_width / 2.0),
                float(center_y - box_height / 2.0),
                float(center_x + box_width / 2.0),
                float(center_y + box_height / 2.0),
                float(scores[anchor, row, column]),
            )
        )
    return detections


def maximum_confidence(output: torch.Tensor) -> float:
    """Return the highest objectness-by-class score in the 13x13 YOLO head."""
    values = output.reshape(1, 3, 6, 13, 13).permute(0, 1, 3, 4, 2)[0]
    objectness = values[..., 4] / 2.0 + 0.5
    class_score = values[..., 5] / 2.0 + 0.5
    return float((objectness * class_score).max())


def intersection_over_union(first: tuple[float, ...], second: tuple[float, ...]) -> float:
    left = max(first[0], second[0])
    top = max(first[1], second[1])
    right = min(first[2], second[2])
    bottom = min(first[3], second[3])
    intersection = max(0.0, right - left) * max(0.0, bottom - top)
    first_area = max(0.0, first[2] - first[0]) * max(0.0, first[3] - first[1])
    second_area = max(0.0, second[2] - second[0]) * max(0.0, second[3] - second[1])
    return intersection / max(first_area + second_area - intersection, 1e-9)


def non_max_suppression(
    boxes: list[tuple[float, ...]], iou_threshold: float, max_detections: int
) -> list[tuple[float, ...]]:
    selected: list[tuple[float, ...]] = []
    for candidate in sorted(boxes, key=lambda box: box[4], reverse=True):
        if all(intersection_over_union(candidate, kept) <= iou_threshold for kept in selected):
            selected.append(candidate)
            if len(selected) == max_detections:
                break
    return selected


def restore_coordinates(
    box: tuple[float, ...], ratio: float, padding: tuple[float, float], shape: tuple[int, int]
) -> tuple[int, int, int, int, float]:
    height, width = shape
    x0 = int(round((box[0] - padding[0]) / ratio))
    y0 = int(round((box[1] - padding[1]) / ratio))
    x1 = int(round((box[2] - padding[0]) / ratio))
    y1 = int(round((box[3] - padding[1]) / ratio))
    return (
        max(0, min(width - 1, x0)),
        max(0, min(height - 1, y0)),
        max(0, min(width - 1, x1)),
        max(0, min(height - 1, y1)),
        box[4],
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the LPYOLO 4W4A FINN ONNX in software.")
    parser.add_argument("image", type=Path)
    parser.add_argument("--model", type=Path, default=MODEL_PATH)
    parser.add_argument("--output", type=Path, default=SCRIPT_DIR / "outputs" / "prediction.png")
    parser.add_argument("--confidence", type=float, default=0.30)
    parser.add_argument("--iou", type=float, default=0.10)
    parser.add_argument("--max-detections", type=int, default=20)
    args = parser.parse_args()

    source_bgr = cv2.imread(str(args.image))
    if source_bgr is None:
        raise FileNotFoundError(args.image)
    source_rgb = cv2.cvtColor(source_bgr, cv2.COLOR_BGR2RGB)
    padded_rgb, ratio, padding = letterbox(source_rgb)
    input_tensor = torch.from_numpy(padded_rgb.transpose(2, 0, 1).copy()).unsqueeze(0).float()

    model = FinnOnnxReference(args.model)
    start = time.perf_counter()
    raw_output = model(input_tensor)
    elapsed = time.perf_counter() - start
    candidates = decode(raw_output, args.confidence)
    selected = non_max_suppression(candidates, args.iou, args.max_detections)

    restored = [
        restore_coordinates(box, ratio, padding, source_bgr.shape[:2]) for box in selected
    ]
    result = source_bgr.copy()
    for x0, y0, x1, y1, score in restored:
        cv2.rectangle(result, (x0, y0), (x1, y1), (0, 255, 0), 2)
        cv2.putText(
            result,
            f"face {score:.2f}",
            (x0, max(16, y0 - 4)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 255, 0),
            1,
            cv2.LINE_AA,
        )
        print(f"BOX x0={x0} y0={y0} x1={x1} y1={y1} score={score:.6f}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(args.output), result):
        raise RuntimeError(f"failed to save {args.output}")
    print(
        f"RAW_RANGE={float(raw_output.min()):.6f},{float(raw_output.max()):.6f} "
        f"MAX_SCORE={maximum_confidence(raw_output):.6f} "
        f"CANDIDATES={len(candidates)} DETECTIONS={len(restored)} "
        f"INFERENCE_SECONDS={elapsed:.3f}"
    )
    print(f"OUTPUT={args.output}")


if __name__ == "__main__":
    main()
