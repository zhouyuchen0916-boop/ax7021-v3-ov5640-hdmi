#################  J16 PORT
set_property PACKAGE_PIN V8       [get_ports {cmos1_i2c_sda_io}]
set_property PACKAGE_PIN AA6      [get_ports {cmos1_d[9]}]
set_property PACKAGE_PIN AA7      [get_ports {cmos1_d[8]}]
set_property PACKAGE_PIN AA11     [get_ports {cmos1_i2c_scl_io}]
set_property PACKAGE_PIN AB11     [get_ports {cmos1_d[5]}]
set_property PACKAGE_PIN AB4      [get_ports {cmos1_d[3]}]
set_property PACKAGE_PIN AB5      [get_ports {cmos1_d[4]}]
set_property PACKAGE_PIN AB1      [get_ports {cmos1_d[6]}]
set_property PACKAGE_PIN AB2      [get_ports {cmos1_d[0]}]
set_property PACKAGE_PIN Y4       [get_ports {cmos1_d[7]}]
set_property PACKAGE_PIN AA4      [get_ports {cmos1_d[1]}]
set_property PACKAGE_PIN AB10     [get_ports {cmos1_d[2]}]
set_property PACKAGE_PIN AB9      [get_ports {cmos1_pclk}]
set_property PACKAGE_PIN AA9      [get_ports {cmos1_href}]
set_property PACKAGE_PIN AA8      [get_ports {cmos1_vsync}]
set_property PACKAGE_PIN AB7      [get_ports {cmos_rstn_tri_o[0]}]

set_property IOSTANDARD LVCMOS33 [get_ports {cmos1_i2c_sda_io}]
set_property IOSTANDARD LVCMOS33 [get_ports {cmos1_d[9]}]
set_property IOSTANDARD LVCMOS33 [get_ports {cmos1_d[8]}]
set_property IOSTANDARD LVCMOS33 [get_ports {cmos1_i2c_scl_io}]
set_property IOSTANDARD LVCMOS33 [get_ports {cmos1_d[5]}]
set_property IOSTANDARD LVCMOS33 [get_ports {cmos1_d[3]}]
set_property IOSTANDARD LVCMOS33 [get_ports {cmos1_d[4]}]
set_property IOSTANDARD LVCMOS33 [get_ports {cmos1_d[6]}]
set_property IOSTANDARD LVCMOS33 [get_ports {cmos1_d[0]}]
set_property IOSTANDARD LVCMOS33 [get_ports {cmos1_d[7]}]
set_property IOSTANDARD LVCMOS33 [get_ports {cmos1_d[1]}]
set_property IOSTANDARD LVCMOS33 [get_ports {cmos1_d[2]}]
set_property IOSTANDARD LVCMOS33 [get_ports {cmos1_pclk}]
set_property IOSTANDARD LVCMOS33 [get_ports {cmos1_href}]
set_property IOSTANDARD LVCMOS33 [get_ports {cmos1_vsync}]
set_property IOSTANDARD LVCMOS33 [get_ports {cmos_rstn_tri_o[0]}]

set_property PULLUP true [get_ports cmos1_i2c_scl_io]
set_property PULLUP true [get_ports cmos1_i2c_sda_io]

# OV5640 720p initialization sets PCLK to 84 MHz (ov5640.c, registers 0x3035/0x3036).
# Constrain the external source-synchronous pixel clock so the capture and FIFO write
# domains are included in static timing analysis.
create_clock -name cmos1_pclk -period 11.904762 -waveform {0.000000 5.952381} [get_ports cmos1_pclk]

set_property CLOCK_DEDICATED_ROUTE FALSE [get_nets cmos1_pclk_IBUF]
