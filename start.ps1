# start.ps1
# Hiring Cafe Pipeline Launcher

$ErrorActionPreference = "Stop"

Write-Host "================================================" -ForegroundColor Cyan
Write-Host "   Hiring Cafe Pipeline Launcher (Windows)      " -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan

$ROOT = Get-Location
$VENV_PATH = Join-Path $ROOT "venv\Scripts\python.exe"
$SCRIPT_PATH = Join-Path $ROOT "hiring_cafe_scheduler.py"

# 1. Check for .env file
if (-not (Test-Path ".env")) {
    Write-Host "❌ ERROR: .env file not found. Please create it first." -ForegroundColor Red
    exit 1
}

# 2. Check for virtual environment
if (Test-Path $VENV_PATH) {
    Write-Host "✅ Virtual environment found. Using $VENV_PATH" -ForegroundColor Green
    $PYTHON = $VENV_PATH
} else {
    Write-Host "⚠️  Virtual environment not found at $VENV_PATH. Using system python." -ForegroundColor Yellow
    $PYTHON = "python"
}

# 3. Run the scheduler with --force
Write-Host "🚀 Launching Hiring Cafe Pipeline..." -ForegroundColor Green
& $PYTHON $SCRIPT_PATH --force

Write-Host "================================================" -ForegroundColor Cyan
Write-Host "   Pipeline Finished                            " -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan

pause
