$ErrorActionPreference = "Stop"

if (-not (Test-Path ".venv")) {
    python -m venv .venv
}

.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m PyInstaller `
    --name MoneyManagerDAD `
    --windowed `
    --onedir `
    --clean `
    main.py

Write-Host "Built dist\MoneyManagerDAD\MoneyManagerDAD.exe"

