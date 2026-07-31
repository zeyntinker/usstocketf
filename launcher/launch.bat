@echo off
setlocal
set "ROOT=%~dp0.."
if not exist "%ROOT%\.venv\Scripts\pythonw.exe" (
  powershell -NoProfile -Command "Add-Type -AssemblyName PresentationFramework; [System.Windows.MessageBox]::Show('먼저 setup.bat을 한 번 실행해 주세요.','Sector ETF Leadership')"
  exit /b 1
)
start "" /b "%ROOT%\.venv\Scripts\pythonw.exe" "%ROOT%\launcher\run_app.py"
