@echo off
REM Launches the Return Inventory app in your browser.

cd /d %~dp0

if not exist ".venv" (
    echo Setup hasn't been run yet.
    echo Double-click setup.bat first ^(one time only^), then try this again.
    pause
    exit /b 1
)

call .venv\Scripts\activate.bat
streamlit run app.py
