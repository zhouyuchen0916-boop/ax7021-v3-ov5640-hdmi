#////////////////////////////////////////////////////////////////////////////////
#  project：ov5640_single                                                      //
#                                                                              //
#  Author: JunFN                                                               //
#          853808728@qq.com                                                    //
#          ALINX(shanghai) Technology Co.,Ltd                                  //
#          黑金                                                                //
#     WEB: http://www.alinx.cn/                                                //
#                                                                              //
#////////////////////////////////////////////////////////////////////////////////
#                                                                              //
# Copyright (c) 2017,ALINX(shanghai) Technology Co.,Ltd                        //
#                    All rights reserved                                       //
#                                                                              //
# This source file may be used and distributed without restriction provided    //
# that this copyright statement is not removed from the file and that any      //
# derivative work contains the original copyright notice and the associated    //
# disclaimer.                                                                  //
#                                                                              // 
#////////////////////////////////////////////////////////////////////////////////

#================================================================================
#  Revision History:
#  Date          By            Revision    Change Description
# --------------------------------------------------------------------------------
#  2023/8/22                   1.0          Original
#=================================================================================

#设置项目名称和工作目录
set proj_name "ov5640_single"
set tclpath [pwd]
cd ..
set projpath [pwd]
cd ..
set Vitispath [pwd]
set bdname "design_1"
set validate_only 0
if {[llength $argv] > 0 && [lindex $argv 0] eq "validate"} {
  set validate_only 1
}
#创建工程
#**********************************************************************************************************
create_project -force $proj_name $projpath/$proj_name -part xc7z020clg484-2
# Create 'sources_1' fileset (if not found)
if {[string equal [get_filesets -quiet sources_1] ""]} {
  create_fileset -srcset sources_1
}
file mkdir $projpath/$proj_name/$proj_name.srcs/sources_1/ip
file mkdir $projpath/$proj_name/$proj_name.srcs/sources_1/new
file mkdir $projpath/$proj_name/$proj_name.srcs/sources_1/bd
# Create 'constrs_1' fileset (if not found)
if {[string equal [get_filesets -quiet constrs_1] ""]} {
  create_fileset -constrset constrs_1
}
file mkdir $projpath/$proj_name/$proj_name.srcs/constrs_1/new
# Create 'sim_1' fileset (if not found)
if {[string equal [get_filesets -quiet sim_1] ""]} {
  create_fileset -simset sim_1
}
file mkdir $projpath/$proj_name/$proj_name.srcs/sim_1/new
# 添加板级自定义 IP 和训练模型生成的 HLS IP。
# 首次重建前先运行项目根目录下的 hls/build_hls.bat all。
set hls_ip_repo $Vitispath/hls/tiny_face_hls/solution1/impl/ip
if {![file exists $hls_ip_repo/component.xml]} {
  error "tiny_face_accel IP not found. Run hls/build_hls.bat all first: $hls_ip_repo"
}
set_property ip_repo_paths [list $tclpath/my_ip $hls_ip_repo] [current_project]
update_ip_catalog
# 添加目标框叠加 RTL，供 Block Design 以 Module Reference 使用
add_files -fileset sources_1 -norecurse $tclpath/src/rtl/axis_bbox_overlay.v
update_compile_order -fileset sources_1
#*********************************************************************************************************
#create_bd_design "$bdname"
create_bd_design $bdname
update_compile_order -fileset sources_1
open_bd_design $projpath/$proj_name/$proj_name.srcs/sources_1/bd/$bdname/$bdname.bd
create_bd_cell -type ip -vlnv xilinx.com:ip:processing_system7:5.5 processing_system7_0
source $tclpath/ps_config.tcl
set_ps_config processing_system7_0
source $tclpath/pl_config.tcl
regenerate_bd_layout
validate_bd_design
save_bd_design
if {$validate_only} {
  puts "BD_VALIDATE_ONLY_OK"
  exit
}
make_wrapper -files [get_files $projpath/$proj_name/$proj_name.srcs/sources_1/bd/$bdname/$bdname.bd] -top
add_files -norecurse [glob -nocomplain $projpath/$proj_name/$proj_name.gen/sources_1/bd/$bdname/hdl/*.v]
puts $bdname
append bdWrapperName $bdname "_wrapper"
puts $bdWrapperName
# 设置顶层文件属性
set_property top $bdWrapperName [current_fileset]

#*********************************************************************************************************
#添加约束文件
add_files -fileset constrs_1  -copy_to $projpath/$proj_name/$proj_name.srcs/constrs_1/new -force -quiet [glob -nocomplain $tclpath/src/constraints/*.xdc]
# The hierarchical camera-IP CDC endpoints are available after OOC IP synthesis.
# Keep the targeted CDC exception out of synthesis and apply it in implementation.
set async_clock_xdc [get_files -quiet */async_clock_groups.xdc]
if {[llength $async_clock_xdc] > 0} {
  set_property USED_IN_SYNTHESIS false $async_clock_xdc
  set_property USED_IN_IMPLEMENTATION true $async_clock_xdc
}
# 运行综合、实现和生成比特流（Vivado 2023.1）
# 官方脚本在 wait_on_run 后又手工执行 synth/place/route，可能导致运行状态冲突。
# 此处改为标准 run 流程，并在每一步检查状态。
set jobs 5
launch_runs synth_1 -jobs $jobs
wait_on_run synth_1
set synth_status [get_property STATUS [get_runs synth_1]]
puts "SYNTH_STATUS=$synth_status"
if {![string match "*Complete*" $synth_status]} {
  error "Synthesis failed: $synth_status"
}

launch_runs impl_1 -to_step write_bitstream -jobs $jobs
wait_on_run impl_1
set impl_status [get_property STATUS [get_runs impl_1]]
puts "IMPL_STATUS=$impl_status"
if {![string match "*Complete*" $impl_status]} {
  error "Implementation failed: $impl_status"
}

# 生成可复核的实现报告
open_run impl_1
set report_dir $projpath/reports
file mkdir $report_dir
report_timing_summary -delay_type min_max -report_unconstrained -check_timing_verbose \
  -max_paths 10 -input_pins -file $report_dir/timing_summary.rpt
report_utilization -hierarchical -file $report_dir/utilization_hierarchical.rpt
report_drc -file $report_dir/drc.rpt
report_methodology -file $report_dir/methodology.rpt
report_cdc -details -file $report_dir/cdc.rpt

# 导出本次构建得到的 bit 和含 bitstream 的 XSA
set bit_file $projpath/$proj_name/$proj_name.runs/impl_1/$bdWrapperName.bit
if {![file exists $bit_file]} {
  error "Bitstream not found: $bit_file"
}
file copy -force $bit_file $projpath/$bdWrapperName.bit
write_hw_platform -fixed -include_bit -force -file $Vitispath/Vitis/$bdWrapperName.xsa

puts "BUILD_OK"
puts "BIT_FILE=$projpath/$bdWrapperName.bit"
puts "XSA_FILE=$Vitispath/Vitis/$bdWrapperName.xsa"


