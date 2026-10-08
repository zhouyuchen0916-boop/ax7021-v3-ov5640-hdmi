from __future__ import annotations

import argparse
import time
from datetime import datetime
from pathlib import Path

import cv2


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect clean frames from the HDMI USB capture card.")
    parser.add_argument("--device", type=int, default=0, help="OpenCV/DirectShow device index")
    parser.add_argument("--count", type=int, default=80)
    parser.add_argument("--output", type=Path, default=Path("training/field_dataset/images"))
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    capture = cv2.VideoCapture(args.device, cv2.CAP_DSHOW)
    capture.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    if not capture.isOpened():
        raise SystemExit(
            f"cannot open video device {args.device}; close OBS or try -Device 1, 2, or 3"
        )

    saved = 0
    last_saved_at = 0.0
    window = "AX7021 HDMI field capture"
    print("Live HDMI capture opened. SPACE=save, Q=finish. Do not wear hats, glasses, sunglasses, or masks.")
    try:
        while saved < args.count:
            ok, frame = capture.read()
            if not ok:
                raise RuntimeError("HDMI capture card stopped returning frames")
            preview = frame.copy()
            cv2.putText(
                preview,
                f"SPACE save   Q finish   {saved}/{args.count}",
                (24, 42),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.0,
                (0, 255, 0),
                2,
                cv2.LINE_AA,
            )
            cv2.imshow(window, preview)
            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27):
                break
            if key == 32 and time.monotonic() - last_saved_at > 0.4:
                saved += 1
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
                path = args.output / f"field_{saved:03d}_{timestamp}.png"
                if not cv2.imwrite(str(path), frame):
                    raise RuntimeError(f"failed to save {path}")
                last_saved_at = time.monotonic()
                print(f"Saved {saved}/{args.count}: {path}")
    finally:
        capture.release()
        cv2.destroyAllWindows()

    print(f"CAPTURE_FINISHED saved={saved} output={args.output}")


if __name__ == "__main__":
    main()
