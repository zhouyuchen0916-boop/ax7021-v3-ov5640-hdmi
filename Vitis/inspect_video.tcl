connect
targets -set -nocase -filter {name =~ "ARM*#0"}
catch {stop}
puts "VDMA_BEGIN"
puts [mrd -force 0x43000000 16]
puts "VDMA_END"
puts "VTC_BEGIN"
puts [mrd -force 0x43C00000 8]
puts "VTC_END"
puts "DYNCLK_BEGIN"
puts [mrd -force 0x43C10000 8]
puts "DYNCLK_END"
puts "GPIO_BEGIN"
puts [mrd -force 0x41200000 2]
puts [mrd -force 0x41210000 2]
puts [mrd -force 0x41220000 4]
puts "GPIO_END"
disconnect
