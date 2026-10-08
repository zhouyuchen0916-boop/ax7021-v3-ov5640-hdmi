set bbox_x_gpio 0x41220000

connect
targets -set -nocase -filter {name =~ "ARM*#0"}
set current [lindex [mrd -force -value $bbox_x_gpio] 0]
set disabled [expr {$current & 0x7FFFFFFF}]
mwr -force $bbox_x_gpio $disabled
set verified [lindex [mrd -force -value $bbox_x_gpio] 0]
puts "BBOX_DISABLED=[format 0x%08X $verified]"
disconnect

if {$verified & 0x80000000} {
    error "failed to disable bounding-box overlay"
}
