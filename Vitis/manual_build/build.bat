@ECHO OFF
SETLOCAL

IF NOT EXIST "..\design_1_wrapper\ps7_cortexa9_0\standalone_domain\bsp\ps7_cortexa9_0\lib\libxil.a" (
  ECHO ERROR: BSP library is missing. Generate the platform before running this script.
  EXIT /B 2
)

CALL "D:\Xilinx\Vitis\2023.1\settings64.bat"

REM Avoid the Vitis 2023.1 gnuwin rm.exe DLL relocation failure on newer
REM Windows builds.  Use native cmd.exe file operations for a clean rebuild.
IF EXIST "build" RMDIR /S /Q "build"
IF EXIST "an5642_single.elf" DEL /Q "an5642_single.elf"
MKDIR "build"
make
SET BUILD_RC=%ERRORLEVEL%

REM arm-none-eabi-size can hit the same host DLL relocation failure after a
REM successful link.  A newly-created ELF is the authoritative build result.
IF EXIST "an5642_single.elf" EXIT /B 0
EXIT /B %BUILD_RC%
