set script_dir [file dirname [file normalize [info script]]]
cd $script_dir
set mode "all"
if {[llength $argv] > 0} {
    set requested_mode [lindex $argv end]
    if {$requested_mode eq "csim" || $requested_mode eq "csynth" || $requested_mode eq "export" || $requested_mode eq "all"} {
        set mode $requested_mode
    }
}
puts "HLS_MODE=$mode HLS_ARGV=$argv"

if {$mode eq "export"} {
    open_project tiny_face_hls
    open_solution solution1
    file mkdir output
    if {[catch {export_design -format ip_catalog -rtl verilog -output output/tiny_face_accel.zip} export_error]} {
        # Vitis HLS has already emitted impl/ip at this point. On this Windows
        # host its child Vivado launcher cannot finish IP-XACT packaging, so
        # run_vitis_hls.ps1 completes run_ippack.tcl with Vivado directly.
        puts "HLS_EXPORT_PACKAGE_DEFERRED=$export_error"
    }
    exit
}

open_project -reset tiny_face_hls
set_top tiny_face_accel
add_files src/tiny_face_accel.cpp -cflags "-Isrc"
add_files -tb tb/tiny_face_tb.cpp -cflags "-Isrc -Itb"
open_solution -reset solution1 -flow_target vivado
set_part {xc7z020-clg484-2}
create_clock -period 10 -name default

if {$mode eq "csim" || $mode eq "all"} {
    csim_design
}
if {$mode eq "csynth" || $mode eq "all"} {
    csynth_design
}
if {$mode eq "all"} {
    file mkdir output
    if {[catch {export_design -format ip_catalog -rtl verilog -output output/tiny_face_accel.zip} export_error]} {
        puts "HLS_EXPORT_PACKAGE_DEFERRED=$export_error"
    }
}
exit
