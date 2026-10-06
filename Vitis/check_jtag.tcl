puts "XSCT_START"
flush stdout
connect
puts "JTAG_CHAIN_BEGIN"
set jtag_list [jtag targets]
if {$jtag_list eq ""} {
    puts "<no JTAG devices detected>"
} else {
    puts $jtag_list
}
puts "JTAG_CHAIN_END"
puts "JTAG_TARGETS_BEGIN"
set target_list [targets]
if {$target_list eq ""} {
    puts "<no XSCT targets detected>"
} else {
    puts $target_list
}
puts "JTAG_TARGETS_END"
disconnect
