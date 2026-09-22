@echo off
setlocal
set "APP=%~dp0..\..\dist\BKPOS\BKPOS.exe"
if not exist "%APP%" (
    echo BKPOS.exe has not been built yet.
    echo Run MAKE_BKPOS_INSTALLER.bat first.
    exit /b 1
)
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ws=New-Object -ComObject WScript.Shell; $s=$ws.CreateShortcut([Environment]::GetFolderPath('Desktop')+'\BKPOS.lnk'); $s.TargetPath='%APP%'; $s.WorkingDirectory='%~dp0..\..\dist\BKPOS'; $s.IconLocation='%APP%,0'; $s.Save()"
echo Desktop shortcut created: BKPOS.lnk
exit /b 0
