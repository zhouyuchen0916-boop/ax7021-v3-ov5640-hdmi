param(
    [ValidateRange(1, 100)]
    [int]$Target = 20
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pairsRoot = Join-Path $PSScriptRoot 'pairs'
$leftDir = Join-Path $pairsRoot 'left'
$rightDir = Join-Path $pairsRoot 'right'
$rejectedDir = Join-Path $pairsRoot 'rejected'
$captureScript = Join-Path $PSScriptRoot 'capture_pair.bat'
$validator = Join-Path $PSScriptRoot 'validate_pair.py'
$python = 'D:\Python\python.exe'

New-Item -ItemType Directory -Force -Path $leftDir, $rightDir, $rejectedDir | Out-Null

function Get-ValidIndices {
    $indices = @()
    Get-ChildItem -LiteralPath $leftDir -Filter 'calibration_*.png' -File | ForEach-Object {
        if ($_.Name -match '^calibration_(\d{3})\.png$') {
            $rightPath = Join-Path $rightDir $_.Name
            if (Test-Path -LiteralPath $rightPath) {
                $indices += [int]$Matches[1]
            }
        }
    }
    return @($indices | Sort-Object -Unique)
}

function Move-RejectedPair([string]$name) {
    $stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
    $leftPath = Join-Path $leftDir "$name.png"
    $rightPath = Join-Path $rightDir "$name.png"
    if (Test-Path -LiteralPath $leftPath) {
        Move-Item -LiteralPath $leftPath -Destination (Join-Path $rejectedDir "${name}_${stamp}_left.png")
    }
    if (Test-Path -LiteralPath $rightPath) {
        Move-Item -LiteralPath $rightPath -Destination (Join-Path $rejectedDir "${name}_${stamp}_right.png")
    }
}

Push-Location $projectRoot
try {
    Write-Host 'AX7021 stereo checkerboard collector'
    Write-Host 'Keep the board fully visible in both cameras.'
    Write-Host 'Press Enter to capture one pair, or Q then Enter to stop.'

    while ($true) {
        $valid = @(Get-ValidIndices)
        if ($valid.Count -ge $Target) {
            Write-Host "COLLECTION_COMPLETE valid=$($valid.Count) target=$Target"
            break
        }

        $nextIndex = 1
        if ($valid.Count -gt 0) {
            $nextIndex = [int](($valid | Measure-Object -Maximum).Maximum) + 1
        }
        $name = 'calibration_{0:D3}' -f ([int]$nextIndex)
        Write-Host 'Place the checkerboard in BOTH camera views now.'
        Write-Host 'Keep it fully visible and still until PAIR_ACCEPTED or PAIR_REJECTED appears.'
        $answer = Read-Host "Ready for $name ($($valid.Count)/$Target). Press Enter to capture or Q to stop"
        if ($answer -match '^[Qq]$') {
            Write-Host "COLLECTION_STOPPED valid=$($valid.Count) target=$Target"
            break
        }

        & $captureScript $name
        if ($LASTEXITCODE -ne 0) {
            Write-Host "CAPTURE_FAILED name=$name exit=$LASTEXITCODE"
            continue
        }

        $leftPath = Join-Path $leftDir "$name.png"
        $rightPath = Join-Path $rightDir "$name.png"
        & $python $validator --left $leftPath --right $rightPath
        if ($LASTEXITCODE -eq 0) {
            $valid = @(Get-ValidIndices)
            Write-Host "PAIR_ACCEPTED name=$name progress=$($valid.Count)/$Target"
            Write-Host 'Move and tilt the checkerboard before the next capture.'
        } else {
            Move-RejectedPair $name
            Write-Host "PAIR_REJECTED name=$name. Reposition the board and retry."
        }
    }
} finally {
    Pop-Location
}
