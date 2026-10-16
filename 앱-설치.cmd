@echo off
cd /d "%~dp0"
rem Use the Python launcher (python.org install) or python (Microsoft Store install).
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY (
  where python >nul 2>nul && python -c "import sys" >nul 2>nul && set "PY=python"
)
if not defined PY (
  echo Install Python 3.10 or newer from python.org or the Microsoft Store, then retry.
  pause
  exit /b 1
)
%PY% -m venv .venv
if errorlevel 1 (
  echo Could not create the virtual environment.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
  pause
  exit /b 1
)
echo Setup complete. Run the app launcher.
pause
