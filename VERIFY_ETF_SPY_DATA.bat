@echo off
setlocal
cd /d "%~dp0"
py -3.12 scripts\verify_data.py
if errorlevel 1 (
 echo ERROR: Verification failed. Do NOT upload incomplete data.
 pause
 exit /b 1
)
pause
