# bbox_ctrl is clocked by FCLK_CLK0 (100 MHz), while the overlay consumes the
# static coordinates on FCLK_CLK1 (125 MHz).  The *_meta registers are
# the first stage of explicit two-flop synchronizers in axis_bbox_overlay.
set_false_path -to [get_pins -hier -quiet -filter {
  NAME =~ *bbox_overlay_0/inst/cfg_x0_meta_reg*/D ||
  NAME =~ *bbox_overlay_0/inst/cfg_y0_meta_reg*/D ||
  NAME =~ *bbox_overlay_0/inst/cfg_x1_meta_reg*/D ||
  NAME =~ *bbox_overlay_0/inst/cfg_y1_meta_reg*/D ||
  NAME =~ *bbox_overlay_0/inst/cfg_x2_meta_reg*/D ||
  NAME =~ *bbox_overlay_0/inst/cfg_y2_meta_reg*/D
}]
