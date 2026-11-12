Set-Location $PSScriptRoot

$env:MOCK_MODE = "true"
$env:APP_ENV = "development"

Write-Host "Starting SDE-4 Backend in MOCK MODE..." -ForegroundColor Green

if (Test-Path ".\.venv\Scripts\python.exe") {
    & ".\.venv\Scripts\python.exe" -m uvicorn app.main:app --reload
}
else {
    python -m uvicorn app.main:app --reload
}