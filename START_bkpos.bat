@echo off
setlocal
cd /d "%~dp0"
if not exist "app.py" (
  echo BKPOS app.py was not found in this folder.
  pause
  exit /b 1
)
python app.py
if errorlevel 1 (
  echo.
  echo BKPOS closed with an error. Keep this window open so the traceback can be copied.
  pause
)
