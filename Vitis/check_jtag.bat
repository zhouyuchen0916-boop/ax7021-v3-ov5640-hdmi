@ECHO OFF
SETLOCAL
IF NOT DEFINED PROCESSOR_ARCHITECTURE SET PROCESSOR_ARCHITECTURE=AMD64
FOR %%I IN ("%~dp0..") DO SET PROJECT_ROOT=%%~fI
IF NOT EXIST "Q:\Vitis\check_jtag.tcl" SUBST Q: "%PROJECT_ROOT%"
IF NOT EXIST "Q:\Vitis\check_jtag.tcl" (
  ECHO ERROR: failed to map the project root to Q:.
  EXIT /B 2
)
IF NOT EXIST "Q:\Vitis\tmp" MKDIR "Q:\Vitis\tmp"
SET TEMP=Q:\Vitis\tmp
SET TMP=Q:\Vitis\tmp
PUSHD "Q:\Vitis"
CALL "D:\Xilinx\Vitis\2023.1\bin\xsct.bat" "Q:\Vitis\check_jtag.tcl" > "%TEMP%\check_jtag.log" 2>&1
SET CHECK_RC=%ERRORLEVEL%
TYPE "%TEMP%\check_jtag.log"
ECHO XSCT_EXIT_CODE=%CHECK_RC%
POPD
EXIT /B %CHECK_RC%
