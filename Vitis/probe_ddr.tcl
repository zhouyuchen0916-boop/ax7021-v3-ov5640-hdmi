set root Q:
set bit_file "$root/Vivado/design_1_wrapper.bit"
set ps_init "$root/Vitis/design_1_wrapper/hw/ps7_init.tcl"

connect
targets -set -nocase -filter {name =~ "ARM*#0"}
catch {stop}
rst -system
after 1000
fpga $bit_file
source $ps_init
ps7_init
ps7_post_config
catch {stop}

puts "DDR_PROBE_BEGIN"
foreach address {0x00110040 0x00800000 0x008F9080 0x008F9BF0 0x00900000 0x00FFFFFF 0x01000000} {
    puts "ADDR=$address"
    set write_value 0xA5A50000
    mwr $address $write_value
    puts "READBACK="
    puts [mrd $address]
    mwr $address 0x00000000
    puts "ZERO="
    puts [mrd $address]
}
puts "DDR_PROBE_END"
disconnect
