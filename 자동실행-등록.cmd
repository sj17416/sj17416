@echo off
chcp 65001 >nul
cd /d "%~dp0"
rem Windows 로그인 시 BlogFlow를 창 없이(백그라운드) 시작하도록 시작프로그램에 등록합니다.
rem 해제: 이 파일을 다시 실행하고 "해제"를 선택하거나, shell:startup 폴더의 BlogFlow 자동실행 바로가기를 삭제하세요.
set "LINK=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\BlogFlow 자동실행.lnk"
if exist "%LINK%" (
  choice /c YN /m "이미 등록되어 있습니다. 등록을 해제할까요? (Y=해제, N=유지)"
  if errorlevel 2 exit /b 0
  del "%LINK%"
  echo 시작프로그램 등록을 해제했습니다.
  pause
  exit /b 0
)
if exist "BlogFlow.exe" (
  set "TARGET=%~dp0BlogFlow.exe"
  set "ARGS=--background"
) else if exist ".venv\Scripts\pythonw.exe" (
  set "TARGET=%~dp0.venv\Scripts\pythonw.exe"
  set "ARGS=studio.py --background"
) else (
  echo BlogFlow.exe 또는 .venv 를 찾지 못했습니다. 앱-설치.cmd 를 먼저 실행하세요.
  pause
  exit /b 1
)
powershell -NoProfile -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut($env:LINK);$s.TargetPath=$env:TARGET;$s.Arguments=$env:ARGS;$s.WorkingDirectory='%~dp0';$s.Save()"
if errorlevel 1 (
  echo 등록에 실패했습니다.
  pause
  exit /b 1
)
echo 등록했습니다. 다음 Windows 로그인부터 BlogFlow가 백그라운드에서 자동화를 실행합니다.
echo 창을 열려면 BlogFlow를 평소처럼 실행하세요. 실행 중인 앱 화면이 열립니다.
pause
