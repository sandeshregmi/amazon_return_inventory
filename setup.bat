@echo off
REM One-time setup: creates a private Python environment in this folder
REM and installs everything the app needs. Safe to run more than once.

cd /d %~dp0

echo Setting up Return Inventory...
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo Python was not found on this computer.
    echo Install it from https://python.org - during install, check the box
    echo that says "Add Python to PATH" - then run this script again.
    pause
    exit /b 1
)

python -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet

echo.
echo Setup complete.
echo Double-click run.bat to launch the app from now on.
pause
