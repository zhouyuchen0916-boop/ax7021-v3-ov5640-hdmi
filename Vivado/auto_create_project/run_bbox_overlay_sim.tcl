set script_dir [file dirname [file normalize [info script]]]
set sim_dir "$script_dir/sim"
set sim_project "$sim_dir/bbox_overlay_sim_project"

create_project bbox_overlay_sim $sim_project -part xc7z020clg484-2 -force
add_files -fileset sources_1 "$script_dir/src/rtl/axis_bbox_overlay.v"
add_files -fileset sim_1 "$sim_dir/tb_axis_bbox_overlay.v"
set_property top tb_axis_bbox_overlay [get_filesets sim_1]
set_property xsim.simulate.runtime all [get_filesets sim_1]
update_compile_order -fileset sources_1
update_compile_order -fileset sim_1

launch_simulation -simset sim_1 -mode behavioral
close_sim
set sim_log "$sim_project/bbox_overlay_sim.sim/sim_1/behav/xsim/simulate.log"
set log_handle [open $sim_log r]
set log_text [read $log_handle]
close $log_handle
if {[string first "BBOX_SIM_PASS" $log_text] < 0} {
  error "Bounding-box self-check did not pass. See $sim_log"
}
puts "BBOX_SIM_SCRIPT_OK"
close_project
