@echo off
:: =====================================================================
:: run_scheduled.bat — Hiring Cafe Daily Pipeline Launcher
:: Registered in Windows Task Scheduler as hiring_cafe_job_extractor
:: Runs daily at 04:01 AM
:: =====================================================================
cd /d "%~dp0"

:: Set UTF-8 encoding so emoji and Unicode print correctly
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

:: Ensure the logs directory exists
if not exist "logs\" mkdir "logs"

:: Date-stamped log file so each daily run is preserved separately
set LOGFILE=logs\scheduler_%date:~-4%-%date:~3,2%-%date:~0,2%.log

echo [%date% %time%] ====================== Starting Scheduler Run ====================== >> "%LOGFILE%"

:: Try local .venv first (hiring-cafe-engine's own venv)
if exist "%~dp0.venv\Scripts\python.exe" (
    echo [%date% %time%] Using local .venv >> "%LOGFILE%"
    "%~dp0.venv\Scripts\python.exe" scheduler_hiring_cafe.py >> "%LOGFILE%" 2>&1
) else if exist "%~dp0venv\Scripts\python.exe" (
    echo [%date% %time%] Using local venv >> "%LOGFILE%"
    "%~dp0venv\Scripts\python.exe" scheduler_hiring_cafe.py >> "%LOGFILE%" 2>&1
) else (
    echo [%date% %time%] Using hiring_cafe_job_extractor venv (fallback) >> "%LOGFILE%"
    call "..\hiring-cafe-engine\venv\Scripts\activate.bat"
    python scheduler_hiring_cafe.py >> "%LOGFILE%" 2>&1
)

echo [%date% %time%] ====================== Scheduler Run Complete ====================== >> "%LOGFILE%"

:: Also append to the rolling combined log
type "%LOGFILE%" >> "logs\scheduler_bat.log"

timeout /t 5

