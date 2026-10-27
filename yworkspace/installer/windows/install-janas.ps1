<#
yWorkspace: Janas-LLM + Qwen3-Coder-Next (80B MoE) on Windows 10/11 x64.

What it does (each step says what it is about to do):
  1. checks the computer (64-bit Windows, memory, free disk space)
  2. downloads Janas-LLM's Windows build from its GitHub releases
  3. downloads Qwen3-Coder-Next (about 48.4 GB, checked with SHA-256 by janas-get)
  4. measures the real speed on this computer (janas-bench)
  5. writes start-janas-server.cmd, which serves the model at http://127.0.0.1:8080/v1,
     and sets yWorkspace's model to "janas-qwen3-coder-next"

Janas-LLM is experimental (GPL-3.0, github.com/prabanta-dev/janas): it uses most free memory for its
expert cache and reads the disk at full speed. This script keeps 8 GB of memory for other programs.

Run in PowerShell:
  powershell -ExecutionPolicy Bypass -File install-janas.ps1
Options: -Dir <folder>  -SkipBench  -Reserve <GiB>
#>
param(
    [string]$Dir = "$env:LOCALAPPDATA\yWorkspace\janas",
    [switch]$SkipBench,
    [int]$Reserve = 8
)
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"   # Invoke-WebRequest is much faster without the progress bar

function Step($n, $text) { Write-Host "`n[$n/5] $text" -ForegroundColor Cyan }

# ---------------------------------------------------------------- 1. checks
Step 1 "Checking this computer"
if (-not [Environment]::Is64BitOperatingSystem) { throw "Janas-LLM needs 64-bit Windows." }
$ramGB = [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB)
Write-Host "  Memory: $ramGB GB"
if ($ramGB -lt 30) { Write-Warning "Qwen3-Coder-Next is meant for 32 GB of memory or more; it may be very slow here." }
New-Item -ItemType Directory -Force -Path $Dir | Out-Null
$drive = (Get-Item $Dir).PSDrive
$freeGB = [math]::Round($drive.Free / 1GB)
Write-Host "  Free space on drive $($drive.Name): $freeGB GB (needed: about 55 GB)"
if ($freeGB -lt 55) { throw "Not enough free disk space in $Dir. Free some space or pass -Dir on another (NVMe) drive." }
$disk = Get-PhysicalDisk | Where-Object { $_.BusType -eq "NVMe" }
if (-not $disk) { Write-Warning "No NVMe SSD found: Janas streams the model from the disk, so a SATA SSD or HDD will be much slower." }

# ---------------------------------------------------------------- 2. Janas-LLM
Step 2 "Downloading Janas-LLM (Windows build, about 26 MB)"
$zip = Join-Path $Dir "janas-windows-x86_64.zip"
Invoke-WebRequest "https://github.com/prabanta-dev/janas/releases/latest/download/janas-windows-x86_64.zip" -OutFile $zip
Expand-Archive $zip -DestinationPath $Dir -Force
$bin = Join-Path $Dir "janas"
foreach ($exe in "janas-get.exe", "janas-bench.exe", "janas-server.exe") {
    if (-not (Test-Path (Join-Path $bin $exe))) { throw "$exe is missing from the download: the package layout may have changed." }
}
Write-Host "  Installed in $bin"

# ---------------------------------------------------------------- 3. the model
Step 3 "Downloading Qwen3-Coder-Next (about 48.4 GB; a stopped download resumes where it stopped)"
$models = Join-Path $Dir "models"
New-Item -ItemType Directory -Force -Path $models | Out-Null
$env:JANAS_MODELS = $models
$list = & (Join-Path $bin "janas-get.exe") list 2>&1 | Out-String
$id = ([regex]::Matches($list, "qwen3-coder-next[a-z0-9.\-]*") | Select-Object -First 1).Value
if (-not $id) { $id = "qwen3-coder-next"; Write-Warning "Could not read the catalog; trying the name '$id'." }
Write-Host "  Model: $id"
& (Join-Path $bin "janas-get.exe") $id --dir $models
if ($LASTEXITCODE -ne 0) { throw "janas-get failed (exit $LASTEXITCODE)." }
$jns = Get-ChildItem $models -Recurse -Filter "*.jns" | Where-Object { $_.Name -like "*coder-next*" -and $_.Name -notlike "*mtp*" } |
    Sort-Object Length -Descending | Select-Object -First 1
if (-not $jns) { throw "The downloaded model file was not found in $models." }
Write-Host "  Model file: $($jns.FullName)"

# ---------------------------------------------------------------- 4. speed
if ($SkipBench) {
    Step 4 "Speed measurement skipped (-SkipBench)"
} else {
    Step 4 "Measuring the speed on this computer (several minutes; the first run also warms the expert cache)"
    & (Join-Path $bin "janas-bench.exe") $id 2>&1 | Tee-Object -FilePath (Join-Path $Dir "bench.txt")
    Write-Host "  Saved to $(Join-Path $Dir 'bench.txt')"
}

# ---------------------------------------------------------------- 5. server + yWorkspace
Step 5 "Writing the server starter and connecting yWorkspace"
$start = Join-Path $Dir "start-janas-server.cmd"
@"
@echo off
rem Serves Qwen3-Coder-Next at http://127.0.0.1:8080/v1 for yWorkspace (only this computer can reach it).
"$bin\janas-server.exe" "$($jns.FullName)" --reserve $Reserve
"@ | Set-Content -Encoding ASCII $start
Write-Host "  Start the model with: $start"
$yw = Get-Command yw -ErrorAction SilentlyContinue
if ($yw) {
    & yw config model janas-qwen3-coder-next
    Write-Host "  yWorkspace now uses janas-qwen3-coder-next. Start the server first, then: yw web"
} else {
    Write-Host "  yWorkspace (yw) not found on PATH: in its settings choose the model 'janas-qwen3-coder-next'."
}
Write-Host "`nDone." -ForegroundColor Green
