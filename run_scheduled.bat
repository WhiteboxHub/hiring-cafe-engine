@echo off
:: Switch to the directory where this batch file is located (hiring-cafe-engine)
cd /d "%~dp0"

:: Set encoding for python output
set PYTHONIOENCODING=utf-8

:: Activate the virtual environment from the other folder
call "..\project-job-application-engine\venv\Scripts\activate.bat"

:: Ensure the logs directory exists
if not exist "logs\" mkdir "logs"

:: Run the scheduler script and log all output
echo [%date% %time%] Starting Scheduler Run >> "logs\scheduler_bat.log"
python scheduler_hiring_cafe.py >> "logs\scheduler_bat.log" 2>&1

:: Optional timeout so you can see the window if you run it manually
timeout /t 5
