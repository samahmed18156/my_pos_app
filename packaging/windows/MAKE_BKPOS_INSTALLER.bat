@echo off
setlocal EnableExtensions
cd /d "%~dp0..\.."
title BKPOS - Make Windows Installer

echo.
echo ============================================================
echo                    BKPOS WINDOWS INSTALLER
echo ============================================================
echo.
echo [1] Windows 10 / Windows 11 (recommended)
echo [2] Windows 7 legacy build (optional)
echo [Q] Quit
echo.
choice /C 12Q /N /M "Select [1/2/Q]: "
if errorlevel 3 exit /b 0
if errorlevel 2 goto LEGACY
call "packaging\windows\build_bkpos_windows10.bat"
exit /b %errorlevel%

:LEGACY
call "packaging\windows\build_bkpos_legacy.bat"
exit /b %errorlevel%
