connect
targets -set -nocase -filter {name =~ "ARM*#0"}
catch {stop}
puts "CPU_PC_BEGIN"
puts [rrd pc]
puts [rrd cpsr]
puts "CPU_PC_END"
puts "APP_DIAG_BEGIN"
puts [mrd 0x0011005C 3]
puts "APP_DIAG_END"
puts "EXCEPTION_ADDRS_BEGIN"
puts [mrd 0x00110044 3]
puts "EXCEPTION_ADDRS_END"
puts "EXCEPTION_TABLE_BEGIN"
puts [mrd 0x0010A20C 16]
puts "EXCEPTION_TABLE_END"
puts "UART0_REGS_BEGIN"
puts [mrd 0xE0000000]
puts [mrd 0xE0000004]
puts [mrd 0xE0000018]
puts [mrd 0xE000002C]
puts [mrd 0xE0000034]
puts "UART0_REGS_END"
puts "UART1_REGS_BEGIN"
puts [mrd 0xE0001000]
puts [mrd 0xE0001004]
puts [mrd 0xE0001018]
puts [mrd 0xE000102C]
puts [mrd 0xE0001034]
puts "UART1_REGS_END"
foreach byte {0x55 0x30 0x0D 0x0A} {
    mwr 0xE0000030 $byte
}
foreach byte {0x55 0x31 0x0D 0x0A} {
    mwr 0xE0001030 $byte
}
con
disconnect
