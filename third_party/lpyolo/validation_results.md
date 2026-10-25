# LPYOLO 4W4A software validation

Historical PC-side reference result only. The current AX7021 bitstream uses TinyFace HLS, and the ONNX weights are not included in the current tree.

Validation date: 2026-10-07

Model SHA-256:

`1D609D9FAFE5082DFCF28F4E4C1E78119E2724379E9018D8E1F77C2A2B3D6743`

## Author sample

- Input: `source/inputs/images/sample.jpg`
- Confidence threshold: 0.02
- Candidates before NMS: 106
- Detections after NMS: 12
- Maximum score: 0.472193
- CPU reference time: 49 ms

## AX7021 OV5640 frame

- Capture path: OV5640 -> S2MM VDMA -> DDR -> JTAG frame dump
- Natural-color preview: `Vitis/captures/frame_bgr.png`
- Confidence threshold: 0.02
- Candidates before NMS: 1
- Detections after NMS: 1
- Box in 1280×720 coordinates: `(657,342)–(939,608)`
- Score: 0.021142
- CPU reference time: 63 ms

The alternate `frame_rgb.png` interpretation swaps red and blue. Its maximum
score is zero on the same frame, so the channel conversion is part of the
validated interface contract.
