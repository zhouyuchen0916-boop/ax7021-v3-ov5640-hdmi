@ECHO OFF
SETLOCAL EnableDelayedExpansion
PUSHD "%~dp0"

IF NOT EXIST "design_1_wrapper\platform.spr" (
  PUSHD "auto_create_vitis"
  CALL build_vitis.bat
  SET PLATFORM_RC=%ERRORLEVEL%
  POPD
  IF NOT "!PLATFORM_RC!"=="0" (
    POPD
    EXIT /B !PLATFORM_RC!
  )
)

CALL "D:\Xilinx\Vitis\2023.1\settings64.bat"
PUSHD "design_1_wrapper\ps7_cortexa9_0\standalone_domain\bsp"
make
SET BSP_RC=%ERRORLEVEL%
POPD
IF NOT "%BSP_RC%"=="0" (
  POPD
  EXIT /B %BSP_RC%
)

PUSHD "manual_build"
CALL build.bat
SET APP_RC=%ERRORLEVEL%
POPD
POPD
EXIT /B %APP_RC%
