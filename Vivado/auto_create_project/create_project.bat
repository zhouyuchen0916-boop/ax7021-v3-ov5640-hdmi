@ECHO OFF
IF NOT DEFINED PROCESSOR_ARCHITECTURE SET PROCESSOR_ARCHITECTURE=AMD64
FOR %%I IN ("%~dp0..\..") DO SET PROJECT_ROOT=%%~fI

REM Vivado 2023.1 can drop the Documents component while normalizing this
REM workspace path. Build through a short SUBST drive to keep Tcl paths valid.
IF NOT EXIST "R:\Vivado\auto_create_project\create_project.tcl" SUBST R: "%PROJECT_ROOT%"
IF NOT EXIST "R:\Vivado\auto_create_project\create_project.tcl" (
  ECHO Failed to map the project root to R:.
  EXIT /B 2
)

PUSHD "R:\Vivado\auto_create_project"
CALL "D:\Xilinx\Vivado\2023.1\bin\vivado.bat" -mode batch -source "R:\Vivado\auto_create_project\create_project.tcl" -nojournal -log "R:\Vivado\auto_create_project\build_ax7021_v3.log"
SET BUILD_RC=%ERRORLEVEL%
POPD
EXIT /B %BUILD_RC%
