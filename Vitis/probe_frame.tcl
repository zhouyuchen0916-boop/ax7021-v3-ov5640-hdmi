connect
targets -set -nocase -filter {name =~ "ARM*#0"}
after 5000
puts "FRAME_SAMPLE_BEGIN"
puts [mrd -force 0x00110C00 16]
puts [mrd -force 0x00210C00 16]
puts [mrd -force 0x00310C00 16]
after 500
puts [mrd -force 0x00110C00 16]
puts [mrd -force 0x00210C00 16]
puts [mrd -force 0x00310C00 16]
puts "FRAME_SAMPLE_END"
disconnect
