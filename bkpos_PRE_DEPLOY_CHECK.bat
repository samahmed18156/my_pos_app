@echo off
setlocal
cd /d "%~dp0"
echo ==========================================
echo BKPOS Production Pre-Deployment Check
 echo ==========================================
python release_check.py
if errorlevel 1 (
  echo.
  echo RELEASE CHECK FAILED - DO NOT DEPLOY THIS BUILD.
  pause
  exit /b 1
)
echo.
echo RELEASE CHECK PASSED.
echo Proceed with the final Windows acceptance checks.
pause
