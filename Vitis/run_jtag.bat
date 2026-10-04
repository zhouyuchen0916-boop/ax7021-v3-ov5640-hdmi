@ECHO OFF
SETLOCAL
IF NOT DEFINED PROCESSOR_ARCHITECTURE SET PROCESSOR_ARCHITECTURE=AMD64
FOR %%I IN ("%~dp0..") DO SET PROJECT_ROOT=%%~fI

IF NOT EXIST "Q:\Vitis\manual_build\an5642_single.elf" SUBST Q: "%PROJECT_ROOT%"
IF NOT EXIST "Q:\Vitis\manual_build\an5642_single.elf" (
  ECHO ERROR: failed to map the project root to Q: or ELF is missing.
  EXIT /B 2
)
IF NOT EXIST "Q:\Vitis\tmp" MKDIR "Q:\Vitis\tmp"
SET TEMP=Q:\Vitis\tmp
SET TMP=Q:\Vitis\tmp

CALL "D:\Xilinx\Vitis\2023.1\bin\xsct.bat" "Q:\Vitis\run_jtag.tcl"
EXIT /B %ERRORLEVEL%
