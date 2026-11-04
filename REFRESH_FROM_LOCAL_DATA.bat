@echo off
setlocal
cd /d "%~dp0"
py -3.12 scripts\refresh_data.py --source "C:\code\DATA\US\data"
if errorlevel 1 (
 echo Data refresh failed; confirm source contains cps2_adjusted\train\YEAR and cps2_adjusted\oos\YEAR.
 pause
 exit /b 1
)
py -3.12 -m unittest discover -s tests -v
pause
