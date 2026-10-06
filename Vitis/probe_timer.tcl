connect
targets -set -nocase -filter {name =~ "ARM*#0"}
puts "GLOBAL_TIMER_BEGIN"
puts [mrd 0xF8F00200 3]
after 200
puts [mrd 0xF8F00200 3]
puts [mrd 0xF8F00208]
puts "GLOBAL_TIMER_END"
disconnect
