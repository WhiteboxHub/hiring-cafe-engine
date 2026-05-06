@REM @echo off
@REM setlocal

@REM :: ============================================================
@REM :: hiring_cafe_scheduler_launcher.bat
@REM :: ============================================================

@REM set "ROOT=C:\Users\remot\Desktop\job_engine\hiring-cafe-engine"
@REM set "VENV=%ROOT%\venv\Scripts\python.exe"
@REM set "SCRIPT=%ROOT%\hiring_cafe_scheduler.py"

@REM :: UTF-8 console for Unicode logging
@REM chcp 65001 > nul
@REM set PYTHONIOENCODING=utf-8
@REM set PYTHONUTF8=1
@REM set SCHEDULER_LAUNCHED=1

@REM if not exist "%VENV%" (
@REM     echo [%date% %time%] ERROR: venv not found at %VENV% >> "%BASE_LOG%"
@REM     echo ERROR: venv not found at %VENV%
@REM     pause
@REM     exit /b 1
@REM )

@REM if not exist "%ROOT%\.env" (
@REM     echo [%date% %time%] ERROR: .env file not found in %ROOT% >> "%BASE_LOG%"
@REM     echo ERROR: .env file not found in %ROOT%
@REM     pause
@REM     exit /b 1
@REM )

@REM if not exist "%ROOT%\logs" mkdir "%ROOT%\logs"

@REM :: Log files
@REM set "BASE_LOG=%ROOT%\logs\scheduler_bat_rolling.log"
@REM set "FULL_LOG=%ROOT%\logs\scheduler_bat.log"

@REM echo [%date% %time%] Starting Hiring Cafe Scheduler (Launcher)... >> "%BASE_LOG%"
@REM echo Starting Hiring Cafe Scheduler (Launcher)...

@REM :: Run Python
@REM "%VENV%" "%SCRIPT%" >> "%BASE_LOG%" 2>&1
@REM set EXIT_CODE=%errorlevel%

@REM echo [%date% %time%] Scheduler finished with exit code %EXIT_CODE% >> "%BASE_LOG%"
@REM echo Scheduler finished with exit code %EXIT_CODE%

@REM :: Append to rolling log
@REM type "%BASE_LOG%" >> "%FULL_LOG%" 2>nul

@REM timeout /t 10
@REM endlocal






@echo off
setlocal

:: ============================================================
:: hiring_cafe_scheduler_launcher.bat
:: ============================================================

set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
set "VENV=%ROOT%\venv\Scripts\python.exe"
set "SCRIPT=%ROOT%\hiring_cafe_scheduler.py"

:: UTF-8 console for Unicode logging
chcp 65001 > nul
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
set SCHEDULER_LAUNCHED=1

if not exist "%VENV%" (
    echo [%date% %time%] ERROR: venv not found at %VENV%
    pause
    exit /b 1
)

if not exist "%ROOT%\.env" (
    echo [%date% %time%] ERROR: .env file not found in %ROOT%
    pause
    exit /b 1
)

if not exist "%ROOT%\logs" mkdir "%ROOT%\logs"

:: ── Log file paths ────────────────────────────────────────────────────────────
set "BASE_LOG=%ROOT%\logs\scheduler_bat_rolling.log"
set "FULL_LOG=%ROOT%\logs\scheduler_bat.log"

:: FIX: Clear the rolling log at the START of each run so it only contains
:: THIS run's output. Without this, every run re-appended the entire old
:: log into FULL_LOG, causing the duplicate entries you saw.
echo. > "%BASE_LOG%"

echo [%date% %time%] Starting Hiring Cafe Scheduler (Launcher)... >> "%BASE_LOG%"
echo Starting Hiring Cafe Scheduler (Launcher)...

:: ── Run Python with --force so the pipeline always executes ──────────────────
:: WHY --force:
::   The orchestrator API (/schedules/due) is not returning workflow ID 9 as
::   due, so without --force the scheduler always exits "No schedule due."
::   --force bypasses that check and runs the pipeline unconditionally.
::   Once the orchestrator issue is diagnosed and fixed, remove --force.
"%VENV%" "%SCRIPT%" --force >> "%BASE_LOG%" 2>&1
set EXIT_CODE=%errorlevel%

echo [%date% %time%] Scheduler finished with exit code %EXIT_CODE% >> "%BASE_LOG%"
echo Scheduler finished with exit code %EXIT_CODE%

:: Append this run's log to the full historical log
type "%BASE_LOG%" >> "%FULL_LOG%" 2>nul

timeout /t 10
endlocal