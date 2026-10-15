################# AN5642 / AX7021 V3.0 J16 PORT

# I2C0 remains routed through the existing extender to HDMI and camera 1.
# Camera 1 is kept in reset-independent wiring so this branch can later grow
# into the full dual-camera design without changing the connector mapping.
set_property PACKAGE_PIN V8       [get_ports {cmos1_i2c_sda_io}]
set_property PACKAGE_PIN AA11     [get_ports {cmos1_i2c_scl_io}]
set_property PACKAGE_PIN AB7      [get_ports {cmos_rstn_tri_o[0]}]

# Camera 2 DVP and independent PS I2C1/EMIO bus.
set_property PACKAGE_PIN V12      [get_ports {cmos2_d[9]}]
set_property PACKAGE_PIN W12      [get_ports {cmos2_i2c_sda_io}]
set_property PACKAGE_PIN U12      [get_ports {cmos2_d[6]}]
set_property PACKAGE_PIN U11      [get_ports {cmos2_i2c_scl_io}]
set_property PACKAGE_PIN U9       [get_ports {cmos2_d[7]}]
set_property PACKAGE_PIN U10      [get_ports {cmos2_d[2]}]
set_property PACKAGE_PIN T6       [get_ports {cmos2_href}]
set_property PACKAGE_PIN R6       [get_ports {cmos2_d[8]}]
set_property PACKAGE_PIN U5       [get_ports {cmos2_d[3]}]
set_property PACKAGE_PIN U6       [get_ports {cmos_rstn_tri_o[1]}]
set_property PACKAGE_PIN U4       [get_ports {cmos2_d[4]}]
set_property PACKAGE_PIN T4       [get_ports {cmos2_d[5]}]
set_property PACKAGE_PIN W10      [get_ports {cmos2_d[1]}]
set_property PACKAGE_PIN W11      [get_ports {cmos2_d[0]}]
set_property PACKAGE_PIN Y10      [get_ports {cmos2_vsync}]
set_property PACKAGE_PIN Y11      [get_ports {cmos2_pclk}]

set_property IOSTANDARD LVCMOS33 [get_ports {cmos1_i2c_sda_io}]
set_property IOSTANDARD LVCMOS33 [get_ports {cmos1_i2c_scl_io}]
set_property IOSTANDARD LVCMOS33 [get_ports {cmos_rstn_tri_o[*]}]
set_property IOSTANDARD LVCMOS33 [get_ports {cmos2_i2c_sda_io}]
set_property IOSTANDARD LVCMOS33 [get_ports {cmos2_i2c_scl_io}]
set_property IOSTANDARD LVCMOS33 [get_ports {cmos2_d[*]}]
set_property IOSTANDARD LVCMOS33 [get_ports {cmos2_href}]
set_property IOSTANDARD LVCMOS33 [get_ports {cmos2_vsync}]
set_property IOSTANDARD LVCMOS33 [get_ports {cmos2_pclk}]

set_property PULLUP true [get_ports cmos1_i2c_scl_io]
set_property PULLUP true [get_ports cmos1_i2c_sda_io]
set_property PULLUP true [get_ports cmos2_i2c_scl_io]
set_property PULLUP true [get_ports cmos2_i2c_sda_io]

# OV5640 720p initialization sets PCLK to 84 MHz (ov5640.c, 0x3035/0x3036).
create_clock -name cmos2_pclk -period 11.904762 -waveform {0.000000 5.952381} [get_ports cmos2_pclk]

# Y11 follows the vendor AN5642 dual-camera reference and is not a clock-capable pin.
set_property CLOCK_DEDICATED_ROUTE FALSE [get_nets cmos2_pclk_IBUF]
