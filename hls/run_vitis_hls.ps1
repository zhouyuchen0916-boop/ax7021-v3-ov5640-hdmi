param(
    [ValidateSet('csim', 'csynth', 'export', 'all')]
    [string]$Mode = 'all'
)

$ErrorActionPreference = 'Stop'
$hlsRoot = 'D:/Xilinx/Vitis_HLS/2023.1'
$vivadoRoot = 'D:/Xilinx/Vivado/2023.1'
$jreRoot = "$hlsRoot/tps/win64/jre11.0.16_1"
$mingwRoot = "$hlsRoot/tps/mingw/8.3.0/win64.o/nt/bin"
$libraryRoot = "$hlsRoot/lib/win64.o"
$executable = 'D:\Xilinx\Vitis_HLS\2023.1\bin\unwrapped\win64.o\vitis_hls.exe'
$tclScript = (Join-Path $PSScriptRoot 'run_hls.tcl').Replace('\', '/')

if (-not (Test-Path -LiteralPath $executable)) {
    throw "Vitis HLS 2023.1 executable was not found: $executable"
}

$env:RDI_APPROOT = $hlsRoot
$env:HDI_APPROOT = $hlsRoot
$env:RDI_BINROOT = "$hlsRoot/bin"
$env:RDI_PLATFORM = 'win64'
$env:RDI_DATADIR = "$vivadoRoot/data;$hlsRoot/data"
$env:RDI_LIBDIR = $libraryRoot
$env:RDI_BINDIR = "$hlsRoot/bin"
$env:RDI_JAVAROOT = $jreRoot
$env:TCL_LIBRARY = "$hlsRoot/tps/tcl/tcl8.5"
$env:ISL_IOSTREAMS_RSA = "$hlsRoot/tps/isl"
$env:XILINX_HLS = $hlsRoot
$env:XILINX_VIVADO = $vivadoRoot
$env:PATH = "$vivadoRoot/bin;$vivadoRoot/lib/win64.o;$libraryRoot;$jreRoot/bin/server;$jreRoot/bin;$mingwRoot;$hlsRoot/bin;$env:SystemRoot\System32;$env:SystemRoot"

& $executable -f $tclScript $Mode
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

if ($Mode -eq 'export' -or $Mode -eq 'all') {
    $ipDirectory = Join-Path $PSScriptRoot 'tiny_face_hls\solution1\impl\ip'
    $ipPackScript = Join-Path $ipDirectory 'run_ippack.tcl'
    $vivadoLauncher = Join-Path $PSScriptRoot 'run_vivado_2023_1.bat'
    if (-not (Test-Path -LiteralPath $ipPackScript)) {
        throw "HLS did not generate the IP packaging script: $ipPackScript"
    }

    Push-Location $ipDirectory
    try {
        & cmd.exe /d /c $vivadoLauncher -notrace -mode batch -source run_ippack.tcl
        if ($LASTEXITCODE -ne 0) {
            throw "Vivado IP packaging failed with exit code $LASTEXITCODE"
        }
    }
    finally {
        Pop-Location
    }

    $component = Join-Path $ipDirectory 'component.xml'
    $packagedZip = Get-ChildItem -LiteralPath $ipDirectory -Filter '*.zip' |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
    if (-not (Test-Path -LiteralPath $component) -or $null -eq $packagedZip) {
        throw "Vivado finished without a complete packaged IP under $ipDirectory"
    }

    $outputDirectory = Join-Path $PSScriptRoot 'output'
    New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
    $outputZip = Join-Path $outputDirectory 'tiny_face_accel.zip'
    Copy-Item -LiteralPath $packagedZip.FullName -Destination $outputZip -Force
    Write-Host "HLS_IP_COMPONENT=$component"
    Write-Host "HLS_IP_ZIP=$outputZip"
}
