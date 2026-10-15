set root Q:
set frame_words [expr {1280 * 720 * 3 / 4}]

if {![info exists ::env(STEREO_PAIR_NAME)]} {
    error "STEREO_PAIR_NAME is not set"
}
set pair_name $::env(STEREO_PAIR_NAME)
if {![regexp {^[0-9A-Za-z_-]+$} $pair_name]} {
    error "Invalid pair name: $pair_name"
}

set raw_dir "$root/stereo/pairs/raw"
file mkdir $raw_dir
set left_file "$raw_dir/${pair_name}_left.bin"
set right_file "$raw_dir/${pair_name}_right.bin"
set metadata_file "$raw_dir/${pair_name}.txt"

# Camera1 is AXI VDMA2 and Camera2 is AXI VDMA1 in the current XSA.
set camera1_base 0x43020000
set camera2_base 0x43010000

proc read_vdma_state {base} {
    set state [dict create]
    dict set state base $base
    dict set state control [lindex [mrd -force -value [expr {$base + 0x30}]] 0]
    dict set state status [lindex [mrd -force -value [expr {$base + 0x34}]] 0]
    dict set state park [lindex [mrd -force -value [expr {$base + 0x28}]] 0]
    dict set state vsize [lindex [mrd -force -value [expr {$base + 0xA0}]] 0]
    dict set state hsize [lindex [mrd -force -value [expr {$base + 0xA4}]] 0]
    dict set state stride [lindex [mrd -force -value [expr {$base + 0xA8}]] 0]
    set starts [list]
    foreach offset {0xAC 0xB0 0xB4} {
        lappend starts [lindex [mrd -force -value [expr {$base + $offset}]] 0]
    }
    dict set state starts $starts

    # AXI VDMA PARK_PTR_REG bits 28:24 report the active S2MM frame store.
    set current [expr {([dict get $state park] >> 24) & 0x1F}]
    if {$current < 0 || $current > 2} {
        set current 0
    }
    # The previous ring entry is complete even if the active entry is partial.
    set completed [expr {($current + 2) % 3}]
    dict set state current $current
    dict set state completed $completed
    dict set state capture_addr [lindex $starts $completed]
    return $state
}

proc stop_vdma {state} {
    set base [dict get $state base]
    set control [dict get $state control]
    mwr -force [expr {$base + 0x30}] [expr {$control & 0xFFFFFFFE}]
    for {set retry 0} {$retry < 200} {incr retry} {
        set status [lindex [mrd -force -value [expr {$base + 0x34}]] 0]
        if {$status & 0x1} {
            return
        }
        after 5
    }
    error [format "S2MM VDMA at 0x%08X did not halt" $base]
}

proc restore_vdma {state} {
    set base [dict get $state base]
    set starts [dict get $state starts]
    mwr -force [expr {$base + 0x30}] [dict get $state control]
    mwr -force [expr {$base + 0xAC}] [lindex $starts 0]
    mwr -force [expr {$base + 0xB0}] [lindex $starts 1]
    mwr -force [expr {$base + 0xB4}] [lindex $starts 2]
    mwr -force [expr {$base + 0xA8}] [dict get $state stride]
    mwr -force [expr {$base + 0xA4}] [dict get $state hsize]
    # Writing VSIZE last restarts the S2MM transfer.
    mwr -force [expr {$base + 0xA0}] [dict get $state vsize]
}

proc clear_vdma_status {state} {
    set status_addr [expr {[dict get $state base] + 0x34}]
    set status [lindex [mrd -force -value $status_addr] 0]
    # SR error bits 11:4 and interrupt bits 14:12 are write-one-to-clear.
    mwr -force $status_addr [expr {$status | 0x00007FF0}]
}

connect
targets -set -nocase -filter {name =~ "ARM*#0"}
stop
after 50

set camera1_state [read_vdma_state $camera1_base]
set camera2_state [read_vdma_state $camera2_base]
set capture_failed [catch {
    stop_vdma $camera1_state
    stop_vdma $camera2_state

    puts "STEREO_PAIR_CAPTURE_BEGIN"
    puts [format "LEFT_FRAME=f%d ADDR=0x%08X" \
        [dict get $camera1_state completed] [dict get $camera1_state capture_addr]]
    puts [format "RIGHT_FRAME=f%d ADDR=0x%08X" \
        [dict get $camera2_state completed] [dict get $camera2_state capture_addr]]

    mrd -force -bin -file $left_file [dict get $camera1_state capture_addr] $frame_words
    mrd -force -bin -file $right_file [dict get $camera2_state capture_addr] $frame_words

    set metadata [open $metadata_file w]
    puts $metadata "pair=$pair_name"
    puts $metadata [format "left_frame=%d" [dict get $camera1_state completed]]
    puts $metadata [format "left_addr=0x%08X" [dict get $camera1_state capture_addr]]
    puts $metadata [format "right_frame=%d" [dict get $camera2_state completed]]
    puts $metadata [format "right_addr=0x%08X" [dict get $camera2_state capture_addr]]
    close $metadata
} capture_message]

# Always restore both writers and the application, including after a read error.
catch {restore_vdma $camera1_state}
catch {restore_vdma $camera2_state}
after 100
catch {clear_vdma_status $camera1_state}
catch {clear_vdma_status $camera2_state}
after 50
set camera1_restart [lindex [mrd -force -value [expr {$camera1_base + 0x34}]] 0]
set camera2_restart [lindex [mrd -force -value [expr {$camera2_base + 0x34}]] 0]
con
disconnect

puts [format "RESTART_STATUS: camera1=0x%08X camera2=0x%08X" \
    $camera1_restart $camera2_restart]
puts "LEFT_RAW=$left_file"
puts "RIGHT_RAW=$right_file"
puts "STEREO_PAIR_CAPTURE_END"

if {$capture_failed} {
    error $capture_message
}
