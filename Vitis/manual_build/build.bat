@ECHO OFF
SETLOCAL

IF NOT EXIST "..\design_1_wrapper\ps7_cortexa9_0\standalone_domain\bsp\ps7_cortexa9_0\lib\libxil.a" (
  ECHO ERROR: BSP library is missing. Generate the platform before running this script.
  EXIT /B 2
)

CALL "D:\Xilinx\Vitis\2023.1\settings64.bat"
make clean
IF ERRORLEVEL 1 EXIT /B %ERRORLEVEL%
make
EXIT /B %ERRORLEVEL%
