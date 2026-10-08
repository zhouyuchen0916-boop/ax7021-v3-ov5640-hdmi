@echo off
setlocal enabledelayedexpansion
set "HLS_ROOT=D:\Xilinx\Vitis_HLS\2023.1"
set "RDI_PROG=vitis_hls"
set "RDI_USE_JDK11=True"
set "PATH=%HLS_ROOT%\bin;%HLS_ROOT%\tps\win64\msys64\usr\bin;%HLS_ROOT%\tps\win64\msys64\mingw64\bin;%PATH%"
call "%HLS_ROOT%\bin\setupEnv.bat"
call "%HLS_ROOT%\bin\hlsArgs.bat" %*
set "HLS_INTERPRETER=%WINDIR%\System32\cmd.exe"
call "%RDI_BINROOT%\loader.bat" -exec %RDI_PROG% %ALL_HLS_ARGS%
set "RESULT=%ERRORLEVEL%"
endlocal & exit /b %RESULT%
