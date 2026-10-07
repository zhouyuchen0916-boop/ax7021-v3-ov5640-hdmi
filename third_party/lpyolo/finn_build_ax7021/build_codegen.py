"""Prepare LPYOLO for AX7021 and generate HLS C++ without running synthesis."""

from pathlib import Path

import finn.builder.build_dataflow as build
import finn.builder.build_dataflow_config as build_cfg


HERE = Path(__file__).resolve().parent
MODEL = HERE.parent / "model_4w4a" / "4w4a" / "best.finn.onnx"

cfg = build_cfg.DataflowBuildConfig(
    output_dir=str(HERE / "output_codegen"),
    target_fps=18,
    mvau_wwidth_max=10000,
    synth_clk_period_ns=10.0,
    hls_clk_period_ns=10.0,
    fpga_part="xc7z020clg484-2",
    generate_outputs=[build_cfg.DataflowOutputType.ESTIMATE_REPORTS],
    steps=build_cfg.hls_codegen_dataflow_steps,
    verify_steps=None,
    save_intermediate_models=True,
    enable_build_pdb_debug=False,
)

build.build_dataflow_cfg(str(MODEL), cfg)
