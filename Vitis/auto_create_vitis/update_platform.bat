@ECHO OFF
SETLOCAL
IF NOT DEFINED PROCESSOR_ARCHITECTURE SET PROCESSOR_ARCHITECTURE=AMD64
FOR %%I IN ("%~dp0..\..") DO SET PROJECT_ROOT=%%~fI

IF NOT EXIST "P:\Vitis\design_1_wrapper.xsa" SUBST P: "%PROJECT_ROOT%"
IF NOT EXIST "P:\Vitis\design_1_wrapper.xsa" (
  ECHO Failed to map the project root to P:.
  EXIT /B 2
)

PUSHD "P:\Vitis\auto_create_vitis"
CALL "D:\Xilinx\Vitis\2023.1\bin\xsct.bat" "P:\Vitis\auto_create_vitis\update_platform.tcl" > "P:\Vitis\auto_create_vitis\update_platform.log" 2>&1
SET UPDATE_RC=%ERRORLEVEL%
TYPE "P:\Vitis\auto_create_vitis\update_platform.log"
POPD
EXIT /B %UPDATE_RC%
