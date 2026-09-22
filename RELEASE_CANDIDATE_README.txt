BKPOS 10.0.0 — RELEASE CANDIDATE

Build target: Windows 10/11 (64-bit or 32-bit Python supported by PyInstaller)

1. Run packaging\\windows\\MAKE_BKPOS_INSTALLER.bat
2. Choose option 1.
3. The script builds dist\\BKPOS\\BKPOS.exe.
4. If Inno Setup 6 is installed, it creates packaging\\windows\\output\\BKPOS_Setup_Windows10.exe.
5. Install the new build to the default per-user location.
6. Keep the old BKPOS installation until the new build passes final acceptance testing.

The packaged BKPOS database is stored separately under %APPDATA%\\BKPOS and is not part of this source release.
