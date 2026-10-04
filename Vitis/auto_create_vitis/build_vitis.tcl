# Keep the raw script path. On this Windows host, Tcl path normalization can
# incorrectly remove the Documents component from the user profile path.
set tclPath [file dirname [info script]]
set projpath [file dirname $tclPath]
puts "Current workspace is $projpath"
setws $projpath
getws
set xsaName design_1_wrapper
set appName an5642_single

#Create a new platform
platform create -name $xsaName -hw $projpath/$xsaName.xsa -proc ps7_cortexa9_0 -os standalone -arch 32-bit -out $projpath

# Vitis 2023.1 creates the platform, BSP source tree and exported XPFM as part
# of platform create. Application-oriented XSCT commands start a background
# Eclipse connection on this Windows host and can time out. The reproducible
# build therefore compiles the generated BSP and the application with Make;
# see Vitis/build_all.bat and Vitis/manual_build/Makefile.






