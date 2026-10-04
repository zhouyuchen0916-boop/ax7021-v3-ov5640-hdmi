@ECHO OFF
IF NOT DEFINED PROCESSOR_ARCHITECTURE SET PROCESSOR_ARCHITECTURE=AMD64
PUSHD "%~dp0"
CALL "D:\Xilinx\Vivado\2023.1\bin\vivado.bat" -mode batch -source "%~dp0create_project.tcl" -nojournal -log "%~dp0build_ax7021_v3.log"
SET BUILD_RC=%ERRORLEVEL%
POPD
EXIT /B %BUILD_RC%
