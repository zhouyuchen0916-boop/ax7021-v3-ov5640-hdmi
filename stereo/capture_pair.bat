@ECHO OFF
SETLOCAL
IF NOT DEFINED PROCESSOR_ARCHITECTURE SET PROCESSOR_ARCHITECTURE=AMD64
FOR %%I IN ("%~dp0..") DO SET PROJECT_ROOT=%%~fI

IF "%~1"=="" (
  FOR /F %%I IN ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') DO SET STEREO_PAIR_NAME=pair_%%I
) ELSE (
  SET STEREO_PAIR_NAME=%~1
)

IF NOT EXIST "Q:\stereo\capture_pair.tcl" SUBST Q: "%PROJECT_ROOT%"
IF NOT EXIST "Q:\stereo\capture_pair.tcl" (
  ECHO ERROR: failed to map the project root to Q:.
  EXIT /B 2
)
IF NOT EXIST "Q:\Vitis\tmp" MKDIR "Q:\Vitis\tmp"
SET TEMP=Q:\Vitis\tmp
SET TMP=Q:\Vitis\tmp

CALL "D:\Xilinx\Vitis\2023.1\bin\xsct.bat" "Q:\stereo\capture_pair.tcl"
IF ERRORLEVEL 1 EXIT /B %ERRORLEVEL%

"D:\Python\python.exe" "Q:\stereo\frame_pair_to_png.py" --root "Q:\stereo\pairs" --name "%STEREO_PAIR_NAME%"
IF ERRORLEVEL 1 EXIT /B %ERRORLEVEL%

ECHO PAIR_CAPTURE_OK=%STEREO_PAIR_NAME%
ECHO LEFT=Q:\stereo\pairs\left\%STEREO_PAIR_NAME%.png
ECHO RIGHT=Q:\stereo\pairs\right\%STEREO_PAIR_NAME%.png
EXIT /B 0
