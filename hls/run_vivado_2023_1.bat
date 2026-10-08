@echo off
setlocal

rem Codex/PowerShell workers may omit this standard Windows variable.
rem Vivado's loader treats an empty value as an unsupported architecture.
if not defined PROCESSOR_ARCHITECTURE set "PROCESSOR_ARCHITECTURE=AMD64"
rem The redistributable is already present (Vivado GUI runs on this host).
rem Skip the launcher's installer probe, which is unreliable in a headless worker.
set "XIL_PA_NO_REDIST_CHECK=1"

call "D:\Xilinx\Vivado\2023.1\bin\vivado.bat" %*
set "EXIT_CODE=%ERRORLEVEL%"
echo VIVADO_EXIT_CODE=%EXIT_CODE%
exit /b %EXIT_CODE%
