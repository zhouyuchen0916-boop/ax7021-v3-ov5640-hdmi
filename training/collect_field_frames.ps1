param(
    [ValidateRange(1, 500)]
    [int]$Count = 80,
    [ValidateRange(0, 20)]
    [int]$Device = 0,
    [string]$OutputDirectory = "",
    [switch]$ValidateOnly
)

$ErrorActionPreference = "Stop"
if ($ValidateOnly) {
    Write-Output "WINDOWS_POWERSHELL_SCRIPT_OK"
    exit 0
}

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$DisableBoxCommand = Join-Path $ProjectRoot "Vitis\disable_bbox.bat"
$Collector = Join-Path $PSScriptRoot "collect_hdmi_frames.py"
if ([string]::IsNullOrWhiteSpace($OutputDirectory)) {
    $OutputDirectory = Join-Path $PSScriptRoot "field_dataset\images"
}

Write-Host "Closing OBS is required because only one app can open the HDMI capture card."
Write-Host "Disabling the FPGA bounding-box overlay before collecting training images..."
& $DisableBoxCommand
if ($LASTEXITCODE -ne 0) {
    throw "Could not disable the bounding-box overlay. Exit code: $LASTEXITCODE"
}

& "D:\Python\python.exe" $Collector --device $Device --count $Count --output $OutputDirectory
exit $LASTEXITCODE
