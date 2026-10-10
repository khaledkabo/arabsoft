@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
echo ==============================================
echo ARAB SOFT - Professional Service System
 echo Building Windows EXE...
echo ==============================================
where py >nul 2>&1
if errorlevel 1 (
  echo Python is not installed or not in PATH.
  pause
  exit /b 1
)
if not exist .venv py -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r arabsoft_service_system\requirements.txt
python -m PyInstaller --noconfirm --clean --onefile --windowed --name ARAB_SOFT_Service --icon arabsoft_service_system\ARAB_SOFT.ico launcher.py
if errorlevel 1 (
  echo BUILD FAILED.
  pause
  exit /b 1
)
echo.
echo BUILD COMPLETE:
echo %CD%\dist\ARAB_SOFT_Service.exe
pause
endlocal
