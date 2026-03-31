@echo off
setlocal

:: ============================================================
:: hiring_cafe_scheduler_launcher.bat
:: ============================================================

set "ROOT=C:\Users\remot\Desktop\job_engine\hiring-cafe-engine"
set "VENV=%ROOT%\venv\Scripts\python.exe"
set "SCRIPT=%ROOT%\hiring_cafe_scheduler.py"

:: UTF-8 console for Unicode logging
chcp 65001 > nul
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
set SCHEDULER_LAUNCHED=1

if not exist "%VENV%" (
    echo ERROR: venv not found at %VENV%
    pause
    exit /b 1
)

if not exist "%ROOT%\logs" mkdir "%ROOT%\logs"

:: Log files
set "BASE_LOG=%ROOT%\logs\scheduler_bat_rolling.log"
set "FULL_LOG=%ROOT%\logs\scheduler_bat.log"

echo [%date% %time%] Starting Hiring Cafe Scheduler (Launcher)... >> "%BASE_LOG%"
echo Starting Hiring Cafe Scheduler (Launcher)...

:: Run Python
"%VENV%" "%SCRIPT%" >> "%BASE_LOG%" 2>&1
set EXIT_CODE=%errorlevel%

echo [%date% %time%] Scheduler finished with exit code %EXIT_CODE% >> "%BASE_LOG%"
echo Scheduler finished with exit code %EXIT_CODE%

:: Append to rolling log
type "%BASE_LOG%" >> "%FULL_LOG%" 2>nul

timeout /t 10
endlocal