@echo off
cd /d "%~dp0"
py -3 -m venv .venv
if errorlevel 1 (
  echo Install Python 3.10 or newer with the Python launcher, then retry.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
  pause
  exit /b 1
)
echo Setup complete. Open the app launcher.
pause
