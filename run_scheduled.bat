@REM @echo off
@REM :: =====================================================================
@REM :: run_scheduled.bat — Hiring Cafe Daily Pipeline Launcher
@REM :: Registered in Windows Task Scheduler as hiring_cafe_job_extractor
@REM :: Runs daily at 07:30 AM
@REM :: =====================================================================
@REM cd /d "%~dp0"

@REM :: Set UTF-8 encoding so emoji and Unicode print correctly
@REM set PYTHONIOENCODING=utf-8
@REM set PYTHONUTF8=1

@REM :: Ensure the logs directory exists
@REM if not exist "logs\" mkdir "logs"

@REM :: Date-stamped log file so each daily run is preserved separately
@REM set LOGFILE=logs\scheduler_%date:~-4%-%date:~3,2%-%date:~0,2%.log

@REM echo [%date% %time%] ====================== Starting Scheduler Run ====================== >> "%LOGFILE%"

@REM :: Try local .venv first (hiring-cafe-engine's own venv)
@REM if exist "%~dp0.venv\Scripts\python.exe" (
@REM     echo [%date% %time%] Using local .venv >> "%LOGFILE%"
@REM     "%~dp0.venv\Scripts\python.exe" scheduler_hiring_cafe.py >> "%LOGFILE%" 2>&1
@REM ) else if exist "%~dp0venv\Scripts\python.exe" (
@REM     echo [%date% %time%] Using local venv >> "%LOGFILE%"
@REM     "%~dp0venv\Scripts\python.exe" scheduler_hiring_cafe.py >> "%LOGFILE%" 2>&1
@REM ) else (
@REM     echo [%date% %time%] Using hiring_cafe_job_extractor venv (fallback) >> "%LOGFILE%"
@REM     call "%~dp0venv\Scripts\activate.bat"
@REM     python scheduler_hiring_cafe.py >> "%LOGFILE%" 2>&1
@REM )

@REM echo [%date% %time%] ====================== Scheduler Run Complete ====================== >> "%LOGFILE%"

@REM :: Also append to the rolling combined log
@REM type "%LOGFILE%" >> "logs\scheduler_bat.log"

@REM timeout /t 5





@echo off
:: =====================================================================
:: run_scheduled.bat — Hiring Cafe Daily Pipeline Launcher
:: Registered in Windows Task Scheduler as hiring_cafe_job_extractor
:: Runs daily at 09:00 AM and 4:00 PM
:: =====================================================================
cd /d "%~dp0"

:: UTF-8 encoding so emoji and Unicode print correctly
chcp 65001 > nul
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

:: Critical flag — tells browser.py to apply anti-detection Chrome flags.
:: Without this, Chrome launched from Task Scheduler has a different
:: fingerprint than an interactive session and hiring.cafe blocks it.
set SCHEDULER_LAUNCHED=1

:: Ensure logs directory exists
if not exist "logs\" mkdir "logs"

:: Date-stamped log file
set LOGFILE=logs\scheduler_%date:~-4%-%date:~3,2%-%date:~0,2%.log

echo [%date% %time%] ====================== Starting Scheduler Run ====================== >> "%LOGFILE%"
echo [%date% %time%] ====================== Starting Scheduler Run ======================

:: ── Find Python ───────────────────────────────────────────────────────────
if exist "%~dp0.venv\Scripts\python.exe" (
    echo [%date% %time%] Using local .venv >> "%LOGFILE%"
    echo [%date% %time%] Using local .venv
    set PYTHON="%~dp0.venv\Scripts\python.exe"
) else if exist "%~dp0venv\Scripts\python.exe" (
    echo [%date% %time%] Using local venv >> "%LOGFILE%"
    echo [%date% %time%] Using local venv
    set PYTHON="%~dp0venv\Scripts\python.exe"
) else (
    echo [%date% %time%] ERROR: No venv found >> "%LOGFILE%"
    echo [%date% %time%] ERROR: No venv found
    pause
    exit /b 1
)

:: ── Run the scheduler ─────────────────────────────────────────────────────
:: IMPORTANT: Output goes to BOTH the console window AND the log file (tee).
:: The console window must stay open so Chrome inherits a real TTY —
:: piping ONLY to a file (>> logfile 2>&1) closes the TTY and causes
:: hiring.cafe's bot detection to block the scraper.
::
:: We achieve both by running Python normally (console visible) and
:: separately appending the log_echo lines around it.
echo [%date% %time%] Launching hiring_cafe_scheduler.py ... >> "%LOGFILE%"
echo [%date% %time%] Launching hiring_cafe_scheduler.py ...

%PYTHON% hiring_cafe_scheduler.py

set EXIT_CODE=%errorlevel%

echo [%date% %time%] Script exited with code %EXIT_CODE% >> "%LOGFILE%"
echo [%date% %time%] Script exited with code %EXIT_CODE%

if %EXIT_CODE% == 0 (
    echo [%date% %time%] Pipeline finished successfully >> "%LOGFILE%"
    echo [%date% %time%] Pipeline finished successfully
) else (
    echo [%date% %time%] Pipeline FAILED - check logs\scheduler.log for details >> "%LOGFILE%"
    echo [%date% %time%] Pipeline FAILED - check logs\scheduler.log for details
)

echo [%date% %time%] ====================== Scheduler Run Complete ====================== >> "%LOGFILE%"
echo [%date% %time%] ====================== Scheduler Run Complete ======================

:: Append to rolling combined log
type "%LOGFILE%" >> "logs\scheduler_bat.log" 2>nul

:: Window stays open for 10 seconds so you can read the result.
:: Remove this line once confirmed working.
timeout /t 10