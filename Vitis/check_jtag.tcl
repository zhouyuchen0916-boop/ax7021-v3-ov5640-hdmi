puts "XSCT_START"
flush stdout
connect
puts "JTAG_TARGETS_BEGIN"
targets
puts "JTAG_TARGETS_END"
disconnect
