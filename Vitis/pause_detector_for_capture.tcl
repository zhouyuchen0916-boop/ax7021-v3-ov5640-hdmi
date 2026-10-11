set bbox_x_gpio 0x41220000

connect
targets -set -nocase -filter {name =~ "ARM*#0"}

# The video path is already configured in PL and continues running while the
# Cortex-A9 is halted.  Halting prevents the detector loop from re-enabling the
# overlay after the register is cleared.
catch {stop}
set current [lindex [mrd -force -value $bbox_x_gpio] 0]
set disabled [expr {$current & 0x7FFFFFFF}]
mwr -force $bbox_x_gpio $disabled
set verified [lindex [mrd -force -value $bbox_x_gpio] 0]
puts "CAPTURE_MODE_BBOX=[format 0x%08X $verified]"
disconnect

if {$verified & 0x80000000} {
    error "failed to disable bounding-box overlay"
}
puts "CAPTURE_MODE_READY: detector paused, camera and HDMI remain active"
