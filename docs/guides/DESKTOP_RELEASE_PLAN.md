# BKPOS Desktop Release Plan

This project remains the source of truth. Desktop packaging adds deployment
files without removing existing workflows.

## Completed in this packaging phase

- Central writable data directory for packaged builds
- Per-user Windows installation target
- No elevation requested by installer
- 32-bit Python 3.8 build target for Windows 7 SP1 compatibility
- PyInstaller one-folder build
- JasperReports jars included from the existing `jasper_runtime`
- Bundled Java 8 discovery for JasperViewer
- Upgrade-safe database location
- Health Check adjusted for packaged EXE
- Existing project files preserved

## Still requires a Windows build machine

- Install Python 3.8.x 32-bit
- Add a compatible Java 8 runtime under `packaging/windows/vendor/jre8`
- Install Inno Setup 6.2.x
- Run `packaging/windows/build_windows.bat`
- Test the resulting installer on:
  - Windows 7 SP1 32-bit
  - Windows 7 SP1 64-bit
  - Windows 10
  - Windows 11

Do not publish the installer until the Windows 7 print and JasperViewer tests
have passed.
