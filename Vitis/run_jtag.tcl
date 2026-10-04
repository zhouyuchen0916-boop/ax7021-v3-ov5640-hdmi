set root Q:
set bit_file "$root/Vivado/design_1_wrapper.bit"
set elf_file "$root/Vitis/manual_build/an5642_single.elf"
set ps_init "$root/Vitis/design_1_wrapper/hw/ps7_init.tcl"

foreach required_file [list $bit_file $elf_file $ps_init] {
    if {![file exists $required_file]} {
        error "Required file is missing: $required_file"
    }
}

connect
targets -set -nocase -filter {name =~ "ARM*#0"}
rst -system
after 1000

fpga $bit_file
source $ps_init
ps7_init
ps7_post_config
dow $elf_file
con
puts "Application downloaded and started. Open UART at 115200 8N1."
disconnect
