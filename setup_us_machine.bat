@echo off
:: ============================================================
:: setup_us_machine.bat
:: Run this ONCE on the US Windows machine as Administrator
:: It sets up the hiring-cafe-engine and registers Task Scheduler
:: ============================================================

echo.
echo ============================================================
echo  Hiring Cafe Engine - US Machine Setup
echo ============================================================
echo.

:: --- Step 1: Check Python is installed ---
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH.
    echo         Download from: https://www.python.org/downloads/
    echo         Make sure to check "Add Python to PATH" during install!
    pause
    exit /b 1
)
echo [OK] Python found.

:: --- Step 2: Check Chrome is installed ---
if exist "C:\Program Files\Google\Chrome\Application\chrome.exe" (
    echo [OK] Google Chrome found.
) else if exist "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe" (
    echo [OK] Google Chrome found.
) else (
    echo [WARNING] Google Chrome not found at default location.
    echo           Download from: https://www.google.com/chrome/
    echo           Chrome is REQUIRED for the hiring cafe scraper.
    pause
)

:: --- Step 3: Navigate to the hiring-cafe-engine folder ---
cd /d "%~dp0"
echo [OK] Working directory: %CD%

:: --- Step 4: Create virtual environment ---
if not exist ".venv\" (
    echo [SETUP] Creating Python virtual environment...
    python -m venv .venv
    echo [OK] Virtual environment created.
) else (
    echo [OK] Virtual environment already exists.
)

:: --- Step 5: Install dependencies ---
echo [SETUP] Installing Python dependencies...
.venv\Scripts\python.exe -m pip install --upgrade pip --quiet
.venv\Scripts\python.exe -m pip install -r requirements.txt --quiet
echo [OK] Dependencies installed.

:: --- Step 6: Apply production .env ---
if exist ".env.us_machine" (
    echo [SETUP] Applying production .env...
    copy /Y ".env.us_machine" ".env"
    echo [OK] .env configured for production (api.whitebox-learning.com)
) else (
    echo [WARNING] .env.us_machine not found - make sure .env has production AUTH_URL
)

:: --- Step 7: Create logs directory ---
if not exist "logs\" mkdir "logs"
echo [OK] Logs directory ready.

:: --- Step 8: Register Windows Task Scheduler ---
echo.
echo [SETUP] Registering Windows Task Scheduler task...

:: Set the path to this folder
set ENGINE_PATH=%~dp0

:: Create the scheduled task - runs daily at 2:00 AM EST
schtasks /create /tn "hiring_cafe_job_extractor" /tr "cmd.exe /c \"%ENGINE_PATH%run_scheduled.bat\"" /sc daily /st 02:00 /ru "SYSTEM" /rl HIGHEST /f

if %errorlevel% == 0 (
    echo [OK] Task Scheduler registered: "hiring_cafe_job_extractor"
    echo      Runs daily at 2:00 AM
) else (
    echo [WARNING] Task Scheduler registration failed.
    echo          Try running this script as Administrator.
)

:: --- Done ---
echo.
echo ============================================================
echo  Setup Complete!
echo ============================================================
echo.
echo  Next steps:
echo   1. Make sure the WBL backend is deployed at:
echo      https://api.whitebox-learning.com
echo   2. Test manually: double-click run_scheduled.bat
echo   3. Check logs in: logs\scheduler_bat.log
echo.
echo  Task Scheduler: runs daily at 2:00 AM (US Eastern Time)
echo  (2:00 AM EST = 12:30 PM IST)
echo.
pause
