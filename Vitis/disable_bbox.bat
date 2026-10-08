@ECHO OFF
SETLOCAL
FOR %%I IN ("%~dp0..") DO SET PROJECT_ROOT=%%~fI

IF NOT EXIST "Q:\Vitis\disable_bbox.tcl" SUBST Q: "%PROJECT_ROOT%"
IF NOT EXIST "Q:\Vitis\disable_bbox.tcl" (
  ECHO ERROR: failed to map the project root to Q:.
  EXIT /B 2
)

CALL "D:\Xilinx\Vitis\2023.1\bin\xsct.bat" "Q:\Vitis\disable_bbox.tcl"
EXIT /B %ERRORLEVEL%
