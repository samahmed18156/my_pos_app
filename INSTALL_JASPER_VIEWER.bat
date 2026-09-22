@echo off
setlocal

echo ================================================
echo BKPOS - JasperViewer Runtime Installer
echo ================================================
echo.
echo Java is already installed on this PC.
echo BKPOS now needs the JasperReports/JasperViewer runtime.
echo.
echo We will download JasperStarter 3.6.2 from SourceForge.
echo JasperStarter includes the JasperReports libraries and a
 echo Windows launcher that can be used by BKPOS.
echo.
set "URL=https://sourceforge.net/projects/jasperstarter/files/JasperStarter-3.6/jasperstarter-3.6.2-Setup.exe/download"
set "OUT=%TEMP%\jasperstarter-3.6.2-Setup.exe"

echo Downloading JasperStarter...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ProgressPreference='SilentlyContinue'; Invoke-WebRequest -Uri '%URL%' -OutFile '%OUT%'"
if errorlevel 1 (
  echo.
  echo Download failed.
  echo Open this address in your browser and install JasperStarter manually:
  echo %URL%
  pause
  exit /b 1
)

if not exist "%OUT%" (
  echo Installer was not downloaded.
  pause
  exit /b 1
)

echo.
echo Starting JasperStarter installer...
start /wait "JasperStarter Setup" "%OUT%"

echo.
echo Installation finished.
echo Restart BKPOS and try VIEW SELECTED DOCUMENT again.
echo.
pause
