@ECHO OFF
SET VIVADO_BAT=D:\Xilinx\Vivado\2023.1\bin\vivado.bat
IF NOT DEFINED PROCESSOR_ARCHITECTURE SET PROCESSOR_ARCHITECTURE=AMD64
PUSHD "%~dp0"
CALL "%VIVADO_BAT%" -mode batch -source "%~dp0finalize_cdc_fix.tcl" -nojournal -log "%~dp0finalize_cdc_fix.log"
SET BUILD_RC=%ERRORLEVEL%
POPD
EXIT /B %BUILD_RC%
