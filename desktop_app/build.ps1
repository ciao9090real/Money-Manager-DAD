$ErrorActionPreference = "Stop"

$BuildTemp = Join-Path $PSScriptRoot ".tmp_build"
$PytestTemp = Join-Path $BuildTemp ("pytest_" + [Guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force -Path $BuildTemp | Out-Null
New-Item -ItemType Directory -Force -Path $PytestTemp | Out-Null
$env:TEMP = $BuildTemp
$env:TMP = $BuildTemp

if (-not (Test-Path ".venv")) {
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

.\.venv\Scripts\python.exe -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider --basetemp "$PytestTemp"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
.\.venv\Scripts\python.exe -m PyInstaller `
    --name MoneyManager `
    --windowed `
    --onedir `
    --noconfirm `
    --clean `
    main.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Built dist\MoneyManager\MoneyManager.exe"
