# This file is implementation-only because the hierarchical camera IP pins are
# available after out-of-context IP synthesis.
#
# OV5640 pixel data crosses into the AXI video domain through xpm_fifo_async.
# XPM supplies its own point-to-point CDC constraints, so do not cut the two
# clock domains globally.  Only the separately synchronized fifo_ready flag
# needs a false path to the first stage of its two-register synchronizer.
set_false_path \
    -from [get_pins -hier -regexp {.*alinx_ov5640_0/inst/fifo_ready_reg/C}] \
    -to   [get_pins -hier -regexp {.*alinx_ov5640_0/inst/fifo_ready_sync_reg\[0\]/D}]

set_false_path \
    -from [get_pins -hier -regexp {.*alinx_ov5640_1/inst/fifo_ready_reg/C}] \
    -to   [get_pins -hier -regexp {.*alinx_ov5640_1/inst/fifo_ready_sync_reg\[0\]/D}]
