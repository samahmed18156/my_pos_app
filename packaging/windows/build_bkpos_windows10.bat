@echo off
setlocal EnableExtensions
cd /d "%~dp0..\.."
title BKPOS Windows 10/11 Release Build

echo ============================================================
echo                 BKPOS WINDOWS 10/11 BUILD
echo ============================================================
echo.

where py >nul 2>nul
if not errorlevel 1 (set "PY=py") else (
    where python >nul 2>nul
    if errorlevel 1 (echo ERROR: Python was not found.& exit /b 1)
    set "PY=python"
)

%PY% -c "import sys,struct; print('Python:',sys.version); print('Architecture:',struct.calcsize('P')*8,'bit'); raise SystemExit(0 if sys.version_info >= (3,9) and struct.calcsize('P') in (4,8) else 1)"
if errorlevel 1 (echo ERROR: Supported Python 3.9+ 32/64-bit is required.& exit /b 1)

%PY% -m pip install --upgrade pip
if errorlevel 1 exit /b 1
%PY% -m pip install --upgrade pyinstaller
if errorlevel 1 exit /b 1
if exist "packaging\windows\requirements-windows10-build.txt" (
    %PY% -m pip install -r "packaging\windows\requirements-windows10-build.txt"
    if errorlevel 1 exit /b 1
)

if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist "packaging\windows\output" rmdir /s /q "packaging\windows\output"
mkdir "packaging\windows\output"

%PY% -m PyInstaller --clean --noconfirm "packaging\windows\BKPOS_Windows10.spec"
if errorlevel 1 exit /b 1

set "ISCC="
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe
if not defined ISCC if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe
if not defined ISCC (
    echo.
    echo BKPOS.exe built successfully in dist\BKPOS\
    echo Install Inno Setup 6 and rerun this script to create the installer.
    exit /b 2
)

"%ISCC%" "packaging\windows\BKPOS_Windows10.iss"
if errorlevel 1 exit /b 1

echo.
echo ============================================================
echo BKPOS BUILD COMPLETE
echo ============================================================
echo Installer: packaging\windows\output\BKPOS_Setup_Windows10.exe
exit /b 0
