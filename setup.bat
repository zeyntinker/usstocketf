@echo off
setlocal
set "ROOT=%~dp0"
where py >nul 2>nul
if errorlevel 1 (
  echo Python 3.11+ is required. Install it from python.org and run this file again.
  pause
  exit /b 1
)
if not exist "%ROOT%.venv\Scripts\python.exe" py -3 -m venv "%ROOT%.venv"
"%ROOT%.venv\Scripts\python.exe" -m pip install --upgrade pip
"%ROOT%.venv\Scripts\python.exe" -m pip install -r "%ROOT%requirements.txt"
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%launcher\install_desktop_shortcut.ps1"
echo Setup complete. A Sector ETF Leadership shortcut was created on your Desktop.
pause
