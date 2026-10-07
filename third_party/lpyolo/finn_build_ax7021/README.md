# FINN 0.7 build for AX7021

Target FPGA: `xc7z020clg484-2`  
Target accelerator clock: 100 MHz  
Target throughput used for automatic folding: 18 FPS

`build_codegen.py` stops after FINN generates per-layer HLS C++ and estimate
reports. This stage needs Linux and Docker but does not need Vivado inside the
container.

`build_stitched_ip.py` also invokes Vitis/Vivado HLS, sizes FIFOs, packages the
streaming accelerator, and runs out-of-context synthesis. It requires a FINN
0.7-compatible Linux Xilinx tool installation mounted into the container.

From WSL/Linux:

```bash
cd /mnt/c/Users/34249/Documents/ChatGPT/FPGA/projects/ax7021_v3_ov5640_base
bash third_party/lpyolo/finn_build_ax7021/run_codegen.sh
```

Expected first-stage outputs:

- `output_codegen/report/estimate_layer_cycles.json`
- `output_codegen/report/estimate_layer_resources.json`
- `output_codegen/auto_folding_config.json`
- HLS C++ code paths referenced by the final intermediate ONNX model

The stitched IP is integrated into the existing Vivado HDMI project only after
its OOC utilization fits alongside the current camera, two VDMAs, HDMI output,
and bounding-box overlay logic.
