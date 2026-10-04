@ECHO OFF
IF NOT DEFINED PROCESSOR_ARCHITECTURE SET PROCESSOR_ARCHITECTURE=AMD64
FOR %%I IN ("%~dp0..\..") DO SET PROJECT_ROOT=%%~fI

REM Vitis 2023.1 mishandles this host's Documents path and also warns about
REM long project paths. Use a short, persistent SUBST drive for this workspace.
IF NOT EXIST "P:\Vitis\design_1_wrapper.xsa" SUBST P: "%PROJECT_ROOT%"
IF NOT EXIST "P:\Vitis\design_1_wrapper.xsa" (
  ECHO Failed to map the project root to P:.
  EXIT /B 2
)

PUSHD "P:\Vitis\auto_create_vitis"
CALL "D:\Xilinx\Vitis\2023.1\bin\xsct.bat" "P:\Vitis\auto_create_vitis\build_vitis.tcl" > "P:\Vitis\auto_create_vitis\build_vitis.log" 2>&1
SET BUILD_RC=%ERRORLEVEL%
TYPE "P:\Vitis\auto_create_vitis\build_vitis.log"
POPD
EXIT /B %BUILD_RC%
