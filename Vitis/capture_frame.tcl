set root Q:
set frame_addr 0x00110C00
set frame_words [expr {1280 * 720 * 3 / 4}]
set s2mm_control_addr 0x43010030
set s2mm_status_addr 0x43010034
set s2mm_vsize_addr 0x430100A0
set s2mm_hsize_addr 0x430100A4
set s2mm_stride_addr 0x430100A8
set s2mm_start0_addr 0x430100AC
set s2mm_start1_addr 0x430100B0
set s2mm_start2_addr 0x430100B4
set output_dir "$root/Vitis/captures"
set output_file "$output_dir/frame_rgb888.bin"

file mkdir $output_dir
connect
targets -set -nocase -filter {name =~ "ARM*#0"}

set control [lindex [mrd -force -value $s2mm_control_addr] 0]
set vsize [lindex [mrd -force -value $s2mm_vsize_addr] 0]
set hsize [lindex [mrd -force -value $s2mm_hsize_addr] 0]
set stride [lindex [mrd -force -value $s2mm_stride_addr] 0]
set start0 [lindex [mrd -force -value $s2mm_start0_addr] 0]
set start1 [lindex [mrd -force -value $s2mm_start1_addr] 0]
set start2 [lindex [mrd -force -value $s2mm_start2_addr] 0]
set stopped_control [expr {$control & 0xFFFFFFFE}]
mwr -force $s2mm_control_addr $stopped_control

set halted 0
for {set retry 0} {$retry < 100} {incr retry} {
    set status [lindex [mrd -force -value $s2mm_status_addr] 0]
    if {$status & 0x1} {
        set halted 1
        break
    }
    after 10
}

if {!$halted} {
    mwr -force $s2mm_control_addr $control
    disconnect
    error "Camera S2MM VDMA did not halt before frame capture"
}

puts "FRAME_CAPTURE_BEGIN"
puts "ADDR=[format 0x%08X $frame_addr] WORDS=$frame_words"

set capture_failed [catch {
    mrd -force -bin -file $output_file $frame_addr $frame_words
} capture_message]

# AXI VDMA starts a transfer when VSIZE is written.  Restoring only the
# control register leaves the camera frame frozen, so restore the complete
# S2MM configuration and write VSIZE last.
mwr -force $s2mm_control_addr $control
mwr -force $s2mm_start0_addr $start0
mwr -force $s2mm_start1_addr $start1
mwr -force $s2mm_start2_addr $start2
mwr -force $s2mm_stride_addr $stride
mwr -force $s2mm_hsize_addr $hsize
mwr -force $s2mm_vsize_addr $vsize
after 100

set restart_status [lindex [mrd -force -value $s2mm_status_addr] 0]
puts "S2MM_RESTART_STATUS=[format 0x%08X $restart_status]"
puts "OUTPUT=$output_file"
puts "FRAME_CAPTURE_END"
disconnect

if {$capture_failed} {
    error $capture_message
}
