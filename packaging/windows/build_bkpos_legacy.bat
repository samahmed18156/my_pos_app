@echo off
setlocal EnableExtensions
cd /d "%~dp0..\.."
title BKPOS Legacy Windows Build

echo ============================================================
echo                 BKPOS LEGACY WINDOWS BUILD
echo ============================================================
echo.
where python >nul 2>nul
if errorlevel 1 (echo ERROR: Python was not found.& exit /b 1)
python -c "import struct,sys; print('Python bits:',struct.calcsize('P')*8); raise SystemExit(0 if sys.version_info[:2]==(3,8) and struct.calcsize('P')==4 else 1)"
if errorlevel 1 (echo ERROR: This legacy path requires Python 3.8.x 32-bit.& exit /b 1)
if not exist "packaging\windows\vendor\jre8\bin\java.exe" (
    echo ERROR: Missing packaging\windows\vendor\jre8\bin\java.exe
    exit /b 1
)
python -m pip install --upgrade "pip<24.1"
python -m pip install -r "packaging\windows\requirements-windows7-build.txt"
if errorlevel 1 exit /b 1
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist "packaging\windows\output" rmdir /s /q "packaging\windows\output"
mkdir "packaging\windows\output"
python -m PyInstaller --clean --noconfirm "packaging\windows\BKPOS.spec"
if errorlevel 1 exit /b 1
xcopy /E /I /Y "packaging\windows\vendor\jre8" "dist\BKPOS\jre8" >nul
if errorlevel 1 exit /b 1
set "ISCC="
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe
if not defined ISCC if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe
if not defined ISCC (echo ERROR: Inno Setup 6 was not found.& exit /b 1)
"%ISCC%" "packaging\windows\BKPOS.iss"
if errorlevel 1 exit /b 1
echo Installer: packaging\windows\output\BKPOS_Setup_Legacy.exe
exit /b 0
