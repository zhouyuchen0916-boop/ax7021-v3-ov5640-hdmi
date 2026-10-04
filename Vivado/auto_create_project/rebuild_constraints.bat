@ECHO OFF
IF NOT DEFINED PROCESSOR_ARCHITECTURE SET PROCESSOR_ARCHITECTURE=AMD64
PUSHD "%~dp0"
CALL "D:\Xilinx\Vivado\2023.1\bin\vivado.bat" -mode batch -source "%~dp0rebuild_constraints.tcl" -nojournal -log "%~dp0rebuild_constraints.log"
SET BUILD_RC=%ERRORLEVEL%
POPD
EXIT /B %BUILD_RC%
