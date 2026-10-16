@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
  echo Python setup is required. Run app setup first.
  pause
  exit /b 1
)
start "" ".venv\Scripts\pythonw.exe" studio.py
