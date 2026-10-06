set tcl_path [file dirname [info script]]
set vitis_path [file dirname $tcl_path]

setws $vitis_path
platform active design_1_wrapper
platform config -updatehw $vitis_path/design_1_wrapper.xsa
platform generate

puts "PLATFORM_UPDATE_OK"

