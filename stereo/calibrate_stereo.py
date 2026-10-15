from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np


def matrix_list(value: np.ndarray) -> list:
    return np.asarray(value).tolist()


def detect_corners(gray: np.ndarray, pattern: tuple[int, int]) -> np.ndarray | None:
    found, corners = cv2.findChessboardCornersSB(
        gray, pattern, flags=cv2.CALIB_CB_EXHAUSTIVE | cv2.CALIB_CB_ACCURACY
    )
    # ACCURACY upsamples the image and helps real camera frames, but some
    # perfectly sharp/generated boards are rejected by that path. Retry with
    # the regular exhaustive detector before declaring the pair invalid.
    if not found:
        found, corners = cv2.findChessboardCornersSB(
            gray, pattern, flags=cv2.CALIB_CB_EXHAUSTIVE
        )
    if not found:
        return None
    return corners.astype(np.float32)


def main() -> None:
    parser = argparse.ArgumentParser(description="Calibrate the AX7021 AN5642 stereo camera from PNG pairs.")
    parser.add_argument("--pairs", type=Path, default=Path("stereo/pairs"))
    parser.add_argument("--output", type=Path, default=Path("stereo/output"))
    parser.add_argument("--cols", type=int, default=9, help="checkerboard inner-corner columns")
    parser.add_argument("--rows", type=int, default=6, help="checkerboard inner-corner rows")
    parser.add_argument("--square-mm", type=float, default=25.0)
    parser.add_argument("--min-pairs", type=int, default=15)
    args = parser.parse_args()

    pattern = (args.cols, args.rows)
    left_files = {path.stem: path for path in (args.pairs / "left").glob("*.png")}
    right_files = {path.stem: path for path in (args.pairs / "right").glob("*.png")}
    names = sorted(left_files.keys() & right_files.keys())
    if not names:
        raise SystemExit("No matching left/right PNG pairs were found.")

    object_template = np.zeros((args.cols * args.rows, 3), np.float32)
    object_template[:, :2] = np.mgrid[0 : args.cols, 0 : args.rows].T.reshape(-1, 2)
    object_template *= args.square_mm

    object_points: list[np.ndarray] = []
    left_points: list[np.ndarray] = []
    right_points: list[np.ndarray] = []
    accepted: list[str] = []
    rejected: list[str] = []
    image_size: tuple[int, int] | None = None

    preview_dir = args.output / "detections"
    preview_dir.mkdir(parents=True, exist_ok=True)

    for name in names:
        left = cv2.imread(str(left_files[name]), cv2.IMREAD_COLOR)
        right = cv2.imread(str(right_files[name]), cv2.IMREAD_COLOR)
        if left is None or right is None or left.shape != right.shape:
            rejected.append(name)
            continue
        current_size = (left.shape[1], left.shape[0])
        if image_size is None:
            image_size = current_size
        if current_size != image_size:
            rejected.append(name)
            continue

        left_corners = detect_corners(cv2.cvtColor(left, cv2.COLOR_BGR2GRAY), pattern)
        right_corners = detect_corners(cv2.cvtColor(right, cv2.COLOR_BGR2GRAY), pattern)
        if left_corners is None or right_corners is None:
            rejected.append(name)
            continue

        object_points.append(object_template.copy())
        left_points.append(left_corners)
        right_points.append(right_corners)
        accepted.append(name)

        left_preview = left.copy()
        right_preview = right.copy()
        cv2.drawChessboardCorners(left_preview, pattern, left_corners, True)
        cv2.drawChessboardCorners(right_preview, pattern, right_corners, True)
        cv2.imwrite(str(preview_dir / f"{name}_left.jpg"), left_preview)
        cv2.imwrite(str(preview_dir / f"{name}_right.jpg"), right_preview)

    if image_size is None or len(accepted) < args.min_pairs:
        raise SystemExit(
            f"Only {len(accepted)} valid pairs; at least {args.min_pairs} are required. "
            f"Rejected: {len(rejected)}"
        )

    left_rms, left_k, left_d, _, _ = cv2.calibrateCamera(
        object_points, left_points, image_size, None, None
    )
    right_rms, right_k, right_d, _, _ = cv2.calibrateCamera(
        object_points, right_points, image_size, None, None
    )
    criteria = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_MAX_ITER, 200, 1e-7)
    stereo_rms, left_k, left_d, right_k, right_d, rotation, translation, essential, fundamental = (
        cv2.stereoCalibrate(
            object_points,
            left_points,
            right_points,
            left_k,
            left_d,
            right_k,
            right_d,
            image_size,
            criteria=criteria,
            flags=cv2.CALIB_FIX_INTRINSIC,
        )
    )
    rect_left, rect_right, proj_left, proj_right, disparity_to_depth, roi_left, roi_right = (
        cv2.stereoRectify(
            left_k,
            left_d,
            right_k,
            right_d,
            image_size,
            rotation,
            translation,
            flags=cv2.CALIB_ZERO_DISPARITY,
            alpha=0,
        )
    )

    baseline_mm = float(np.linalg.norm(translation))
    result = {
        "image_size": list(image_size),
        "checkerboard_inner_corners": [args.cols, args.rows],
        "square_mm": args.square_mm,
        "accepted_pairs": accepted,
        "rejected_pairs": rejected,
        "left_rms": float(left_rms),
        "right_rms": float(right_rms),
        "stereo_rms": float(stereo_rms),
        "baseline_mm": baseline_mm,
        "left_camera_matrix": matrix_list(left_k),
        "left_distortion": matrix_list(left_d),
        "right_camera_matrix": matrix_list(right_k),
        "right_distortion": matrix_list(right_d),
        "rotation": matrix_list(rotation),
        "translation_mm": matrix_list(translation),
        "essential": matrix_list(essential),
        "fundamental": matrix_list(fundamental),
        "rectification_left": matrix_list(rect_left),
        "rectification_right": matrix_list(rect_right),
        "projection_left": matrix_list(proj_left),
        "projection_right": matrix_list(proj_right),
        "disparity_to_depth": matrix_list(disparity_to_depth),
        "valid_roi_left": list(roi_left),
        "valid_roi_right": list(roi_right),
    }

    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "stereo_calibration.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    np.savez_compressed(
        args.output / "stereo_calibration.npz",
        left_k=left_k,
        left_d=left_d,
        right_k=right_k,
        right_d=right_d,
        rotation=rotation,
        translation=translation,
        rect_left=rect_left,
        rect_right=rect_right,
        proj_left=proj_left,
        proj_right=proj_right,
        disparity_to_depth=disparity_to_depth,
    )

    print(f"STEREO_CALIBRATION_OK pairs={len(accepted)} rejected={len(rejected)}")
    print(f"RMS: left={left_rms:.4f} right={right_rms:.4f} stereo={stereo_rms:.4f}")
    print(f"BASELINE_MM={baseline_mm:.3f}")
    print(f"JSON={args.output / 'stereo_calibration.json'}")
    print(f"NPZ={args.output / 'stereo_calibration.npz'}")


if __name__ == "__main__":
    main()
