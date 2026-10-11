param(
    [int]$Seconds = 20,
    [switch]$NoDownload
)

$ErrorActionPreference = 'Stop'
$port = New-Object System.IO.Ports.SerialPort 'COM3',115200,None,8,one
$port.ReadTimeout = 100
$port.Open()
try {
    $proc = $null
    if (-not $NoDownload) {
        $proc = Start-Process -FilePath $env:ComSpec -ArgumentList '/c','run_jtag.bat' -WorkingDirectory $PSScriptRoot -NoNewWindow -PassThru
    }
    $watch = [Diagnostics.Stopwatch]::StartNew()
    while ($watch.Elapsed.TotalSeconds -lt $Seconds) {
        if ($port.BytesToRead -gt 0) {
            Write-Host -NoNewline $port.ReadExisting()
        }
        Start-Sleep -Milliseconds 50
    }
    if ($null -ne $proc -and -not $proc.HasExited) { $proc.WaitForExit(1000) | Out-Null }
} finally {
    if ($port.IsOpen) { $port.Close() }
}
