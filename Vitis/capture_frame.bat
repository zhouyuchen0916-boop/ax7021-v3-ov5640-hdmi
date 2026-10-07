@ECHO OFF
SETLOCAL
IF NOT DEFINED PROCESSOR_ARCHITECTURE SET PROCESSOR_ARCHITECTURE=AMD64
FOR %%I IN ("%~dp0..") DO SET PROJECT_ROOT=%%~fI

IF NOT EXIST "Q:\Vitis\capture_frame.tcl" SUBST Q: "%PROJECT_ROOT%"
IF NOT EXIST "Q:\Vitis\capture_frame.tcl" (
  ECHO ERROR: failed to map the project root to Q:.
  EXIT /B 2
)

PUSHD "Q:\Vitis"
CALL "D:\Xilinx\Vitis\2023.1\bin\xsct.bat" "Q:\Vitis\capture_frame.tcl"
SET CAPTURE_RC=%ERRORLEVEL%
IF NOT "%CAPTURE_RC%"=="0" (
  POPD
  EXIT /B %CAPTURE_RC%
)
"D:\Python\python.exe" "Q:\Vitis\tools\frame_to_png.py" "Q:\Vitis\captures\frame_rgb888.bin"
SET CONVERT_RC=%ERRORLEVEL%
POPD
EXIT /B %CONVERT_RC%
