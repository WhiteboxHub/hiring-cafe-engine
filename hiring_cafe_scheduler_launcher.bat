@echo off
:: ============================================================
::  hiring_cafe_scheduler_launcher.bat
::
::  Use this .bat file as the Task Scheduler "Action" instead
::  of calling pythonw.exe or python.exe directly.
::
::  WHY THIS EXISTS
::  ───────────────
::  Windows Task Scheduler by default runs tasks in Session 0
::  (the non-interactive system session) with no visible window.
::  Chrome launched from Session 0 has a different automation
::  fingerprint — hiring.cafe's Cloudflare bot detection fires
::  and returns an empty page (0 jobs found).
::
::  This launcher forces the task to run in a visible console
::  window in the current user's desktop session, giving Chrome
::  a real TTY exactly as if you double-clicked the script.
::
::  HOW TO USE IN TASK SCHEDULER
::  ──────────────────────────────
::  Program/script : C:\Windows\System32\cmd.exe
::  Arguments      : /c "C:\path\to\hiring_cafe_scheduler_launcher.bat"
::  Start in       : C:\Users\remot\Desktop\job_engine\hiring-cafe-engine
::
::  IMPORTANT: In the "General" tab of the task:
::    - Check "Run only when user is logged on"   ← critical
::    - Uncheck "Run whether user is logged on or not"
::    - Check "Run with highest privileges" (only if needed)
::
::  With "Run only when user is logged on" the task runs in
::  Session 1 (your desktop session) with a real console,
::  which is exactly what Chrome needs.
:: ============================================================

setlocal

:: ── Project root (edit if your path differs) ─────────────────
set "ROOT=C:\Users\remot\Desktop\job_engine\hiring-cafe-engine"
set "VENV=%ROOT%\venv\Scripts\python.exe"
set "SCRIPT=%ROOT%\hiring_cafe_scheduler.py"

:: ── UTF-8 console ─────────────────────────────────────────────
chcp 65001 > nul
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
set SCHEDULER_LAUNCHED=1

:: ── Activate venv and run ─────────────────────────────────────
if not exist "%VENV%" (
    echo ERROR: venv not found at %VENV%
    pause
    exit /b 1
)

echo [%date% %time%] Starting Hiring Cafe Scheduler...
"%VENV%" "%SCRIPT%"

echo [%date% %time%] Scheduler finished with exit code %errorlevel%

:: Remove the pause below once you have confirmed it works.
:: With pause the window stays open so you can read any errors.
pause
endlocal