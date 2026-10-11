param(
    [ValidateRange(1, 500)]
    [int]$Count = 80,
    [ValidateRange(0, 20)]
    [int]$Device = 0,
    [ValidateSet("face", "background")]
    [string]$Scene = "face",
    [string]$OutputDirectory = "",
    [switch]$ValidateOnly
)

$ErrorActionPreference = "Stop"
if ($ValidateOnly) {
    Write-Output "WINDOWS_POWERSHELL_SCRIPT_OK"
    exit 0
}

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$PauseDetectorCommand = Join-Path $ProjectRoot "Vitis\pause_detector_for_capture.bat"
$ResumeDetectorCommand = Join-Path $ProjectRoot "Vitis\run_jtag.bat"
$Collector = Join-Path $PSScriptRoot "collect_hdmi_frames.py"
if ([string]::IsNullOrWhiteSpace($OutputDirectory)) {
    $OutputDirectory = Join-Path $PSScriptRoot "field_dataset_v2\${Scene}_images"
}

Write-Host "Closing OBS is required because only one app can open the HDMI capture card."
Write-Host "Pausing face detection and disabling the FPGA overlay for clean capture..."
& $PauseDetectorCommand
if ($LASTEXITCODE -ne 0) {
    throw "Could not enter clean capture mode. Exit code: $LASTEXITCODE"
}

$CollectorExitCode = 1
$ResumeExitCode = 1
try {
    & "D:\Python\python.exe" $Collector --device $Device --count $Count --output $OutputDirectory --prefix $Scene
    $CollectorExitCode = $LASTEXITCODE
}
finally {
    Write-Host "Restoring the FPGA face-detection application..."
    & $ResumeDetectorCommand
    $ResumeExitCode = $LASTEXITCODE
}

if ($ResumeExitCode -ne 0) {
    throw "Frame collection ended, but the detector could not be restored. Exit code: $ResumeExitCode"
}
exit $CollectorExitCode
