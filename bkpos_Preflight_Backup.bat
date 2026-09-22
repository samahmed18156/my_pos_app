@echo off
setlocal
cd /d "%~dp0"
python -c "from core.config import DB_PATH; from services.release_hardening import preflight_database,create_release_backup; r=preflight_database(DB_PATH); print(r); raise SystemExit(0 if r['ok'] else 1)"
if errorlevel 1 (
  echo Database preflight FAILED.
  pause
  exit /b 1
)
python -c "from core.config import DB_PATH; from services.release_hardening import create_release_backup; print('Backup:', create_release_backup(DB_PATH,'backups',30))"
if errorlevel 1 (
  echo Backup FAILED.
  pause
  exit /b 1
)
echo Preflight and backup completed successfully.
pause
