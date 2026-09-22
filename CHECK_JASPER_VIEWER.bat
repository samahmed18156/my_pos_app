@echo off
cd /d "%~dp0"
python -c "from jasper_reports.jasper_receipt import jasper_viewer_status; print(jasper_viewer_status()[1])"
pause
