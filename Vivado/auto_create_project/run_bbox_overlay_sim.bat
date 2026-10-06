@ECHO OFF
SETLOCAL
IF NOT DEFINED PROCESSOR_ARCHITECTURE SET PROCESSOR_ARCHITECTURE=AMD64
FOR %%I IN ("%~dp0..\..") DO SET PROJECT_ROOT=%%~fI

IF NOT EXIST "S:\Vivado\auto_create_project\sim\tb_axis_bbox_overlay.v" SUBST S: "%PROJECT_ROOT%"
IF NOT EXIST "S:\Vivado\auto_create_project\sim\tb_axis_bbox_overlay.v" (
  ECHO ERROR: failed to map the project root to S:.
  EXIT /B 2
)

PUSHD "S:\Vivado\auto_create_project"
CALL "D:\Xilinx\Vivado\2023.1\bin\vivado.bat" -mode batch -source "S:\Vivado\auto_create_project\run_bbox_overlay_sim.tcl" -nojournal -log "S:\Vivado\auto_create_project\sim\bbox_overlay_sim.log"
SET RC=%ERRORLEVEL%
POPD
EXIT /B %RC%
