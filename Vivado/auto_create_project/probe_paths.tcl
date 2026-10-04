puts "PWD=[pwd]"
puts "SCRIPT=[info script]"
puts "SCRIPT_NORMALIZED=[file normalize [info script]]"
puts "USERPROFILE=$::env(USERPROFILE)"
if {[info exists ::env(HOME)]} { puts "HOME=$::env(HOME)" }
exit
