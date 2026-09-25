# Build: tests -> dist\DrawGuess.exe (PyInstaller, one file) -> release\DrawGuess-<version>-Setup.exe (NSIS)
#        -> release\DrawGuess-<version>-portable.zip. The version is APP_VERSION in installer.nsi.
# Usage:  powershell -ExecutionPolicy Bypass -File build.ps1   [-SkipTests]
# ASCII only on purpose: Windows PowerShell 5.1 reads BOM-less .ps1 files as ANSI.
# Everything runs in the project's own build_env, never in the global Python.
param([switch]$SkipTests)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$root = $PSScriptRoot

$py = "$root\build_env\Scripts\python.exe"
if (-not (Test-Path $py)) {
    Write-Host "Creating build_env" -ForegroundColor Cyan
    py -3 -m venv "$root\build_env"
    if ($LASTEXITCODE) { throw "venv failed" }
}
& $py -m pip install --disable-pip-version-check -q -r "$root\requirements.txt" pyinstaller pytest hypothesis
if ($LASTEXITCODE) { throw "pip install failed" }

if (-not $SkipTests) {
    & $py -m pytest -q -p no:cacheprovider tests
    if ($LASTEXITCODE) { throw "Tests failed, build stopped" }
}

& $py -m PyInstaller --noconfirm --clean DrawGuess.spec
if ($LASTEXITCODE) { throw "PyInstaller failed" }

$nsis = @("${env:ProgramFiles(x86)}\NSIS\makensis.exe", "$env:ProgramFiles\NSIS\makensis.exe") |
    Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $nsis) { throw "NSIS (makensis.exe) not found" }
New-Item -ItemType Directory -Force release | Out-Null
& $nsis /V2 installer.nsi
if ($LASTEXITCODE) { throw "NSIS failed" }

# Portable = the same single exe in a zip.
$version = [regex]::Match((Get-Content "$root\installer.nsi" -Raw), 'APP_VERSION "([^"]+)"').Groups[1].Value
$zip = "$root\release\DrawGuess-$version-portable.zip"
if (Test-Path $zip) { Remove-Item -Force $zip }
Compress-Archive -Path "$root\dist\DrawGuess.exe" -DestinationPath $zip

Get-ChildItem dist\DrawGuess.exe, release\* |
    Select-Object Name, @{n = "MB"; e = { [math]::Round($_.Length / 1MB, 1) } }
