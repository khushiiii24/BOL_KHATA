@echo off
setlocal
cd /d "%~dp0"
title Bol Khata

rem ---- 1. Find Python ------------------------------------------------------
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY ( where python >nul 2>nul && set "PY=python" )
if not defined PY (
  echo.
  echo  Python is not installed.
  echo  Install Python 3.10 or newer from https://www.python.org/downloads/
  echo  While installing, tick "Add python.exe to PATH". Then double-click start.bat again.
  echo.
  pause
  exit /b 1
)

rem ---- 2. Make a private Python setup (kept outside OneDrive) --------------
set "VENV=%LOCALAPPDATA%\BolKhata\venv"
if not exist "%VENV%\Scripts\python.exe" (
  echo  First-time setup. This takes a minute...
  %PY% -m venv "%VENV%" || ( echo  Could not create the Python setup. & pause & exit /b 1 )
)
"%VENV%\Scripts\python.exe" -m pip install --disable-pip-version-check -q -r requirements.txt
if errorlevel 1 ( echo  Could not install packages. Check your internet and try again. & pause & exit /b 1 )

rem ---- 3. Settings file with your Gnani key --------------------------------
if not exist ".env" (
  copy ".env.example" ".env" >nul
  echo.
  echo  A settings file called .env was created. Notepad will open it now.
  echo  Paste your Gnani API key after GNANI_API_KEY=  then Save and close Notepad.
  echo.
  notepad ".env"
)

rem ---- 4. Close an older Bol Khata that is still running ------------------
rem An old window keeps serving old code on port 8000, and the new one could not start.
for /f "tokens=5" %%p in ('netstat -ano ^| findstr /r /c:":8000 .*LISTENING"') do (
  echo  Closing an older Bol Khata that was still running...
  taskkill /F /PID %%p >nul 2>nul
)

rem ---- 5. Start -----------------------------------------------------------
echo.
echo  Bol Khata is running at  http://localhost:8000
echo  Keep this window open while you use it. Close it to stop.
echo.
start "" cmd /c "timeout /t 3 >nul & start http://localhost:8000"
"%VENV%\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000
pause
