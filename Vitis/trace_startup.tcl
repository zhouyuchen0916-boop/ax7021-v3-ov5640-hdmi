set root Q:
set bit_file "$root/Vivado/design_1_wrapper.bit"
set elf_file "$root/Vitis/manual_build/an5642_single.elf"
set ps_init "$root/Vitis/design_1_wrapper/hw/ps7_init.tcl"

connect
targets -set -nocase -filter {name =~ "ARM*#0"}
rst -system
after 1000
fpga $bit_file
source $ps_init
ps7_init
ps7_post_config
dow $elf_file

foreach address {0x001005D8 0x001005E2 0x001005EC 0x001005F2 0x00108620 0x00108664 0x001005F6 0x0010061C 0x00108918} {
    bpremove -all
    bpadd -addr $address
    con
    after 1000
    catch {stop}
    puts "BREAK_EXPECTED=$address"
    puts [rrd pc]
    puts [rrd r0]
    puts [rrd r2]
    puts [rrd r3]
    puts [rrd r4]
    puts [rrd sp]
    puts [rrd lr]
}

bpremove -all
puts "EXCEPTION_STATE_BEGIN"
puts [rrd pc]
puts [rrd cpsr]
puts [rrd lr]
catch {puts [rrd spsr]}
puts "SVC_STACK_CANDIDATES_BEGIN"
puts [mrd 0x008FCBE8 8]
puts [mrd 0x009033E8 8]
puts "SVC_STACK_CANDIDATES_END"
puts "EXCEPTION_VECTOR_TABLE_BEGIN"
puts [mrd 0x0010A20C 16]
puts "EXCEPTION_VECTOR_TABLE_END"
puts "GIC_REGS_BEGIN"
puts [mrd 0xF8F00100 8]
puts [mrd 0xF8F01000 8]
puts [mrd 0xF8F01080 8]
puts [mrd 0xF8F01200 8]
puts "GIC_REGS_END"
disconnect
