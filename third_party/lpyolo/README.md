# LPYOLO integration for AX7021

This directory contains a historical PC-side LPYOLO 4W4A reference experiment.
The AX7021 bitstream and ELF use the project's TinyFace HLS model, not LPYOLO.
The ONNX weights are not distributed in the current repository tree. To
repeat this optional experiment, obtain the model from the upstream project
and place it at the expected path after checking its usage terms.

## Model

- Source project: `sefaburakokcu/finn-quantized-yolo`
- Archive: `4w4a_onnx.zip`
- Model: `model_4w4a/4w4a/best.finn.onnx`
- SHA-256: `1D609D9FAFE5082DFCF28F4E4C1E78119E2724379E9018D8E1F77C2A2B3D6743`
- Input: one RGB `uint8` image, 416 x 416
- Output: one INT8-compatible detection tensor, 13 x 13 x 18

The original PYNQ-Z2 bitstream is not used on AX7021. The network accelerator
must be regenerated for `xc7z020clg484-2` and integrated into the existing
OV5640-to-DDR-to-HDMI design.

## Software reference inference

```powershell
& 'D:\Python\python.exe' third_party\lpyolo\reference_infer.py `
  Vitis\captures\frame_bgr.png `
  --confidence 0.02 `
  --output third_party\lpyolo\outputs\camera_prediction.png
```

The script implements the FINN `MultiThreshold` nodes in PyTorch so that the
model can be checked on Windows before the FINN hardware build environment is
available.

The DDR dump converter writes two channel interpretations. On the current
AX7021/AN5642 path, `frame_bgr.png` has the natural colors and is the correct
source image for the reference script. OpenCV then performs the same BGR-to-RGB
conversion used by the LPYOLO author's deployment code.

## Verified results

- The author's sample image produces 12 face detections at confidence 0.02.
- A live AX7021 OV5640 frame produces one face detection at confidence 0.02.
- Measured Windows CPU reference inference time is about 50 to 65 ms per frame.

These historical results validate model semantics and preprocessing only. They
do not prove FINN IP timing, resource fit, or board throughput, and they do not
describe the current TinyFace board implementation.

## FINN build targets

The model was originally built with FINN 0.7. The directory
`finn_build_ax7021/` contains two builds:

1. `build_codegen.py` performs FINN graph conversion, folding selection,
   estimates, and HLS C++ generation. It does not invoke Vivado or Vitis HLS.
2. `build_stitched_ip.py` continues through Vitis HLS IP generation, FIFO
   sizing, stitched IP packaging, and out-of-context synthesis for
   `xc7z020clg484-2`.

Both configurations target 18 FPS at a 100 MHz accelerator clock, matching the
published 4W4A target. FINN 0.7 officially uses a Linux Docker environment. The
Windows Vivado project remains the final integration environment.
