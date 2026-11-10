@echo off
setlocal
cd /d "%~dp0"
echo USERM V1.3 ETF-only data refresh. Source: C:\code\DATA\US\data
py -3.12 scripts\refresh_data.py --source "C:\code\DATA\US\data"
if errorlevel 1 (
  echo.
  echo ERROR: ETF refresh failed. Existing snapshot is not intentionally replaced.
  echo First install dependencies: py -3.12 -m pip install -r requirements.txt
  pause
  exit /b 1
)
echo.
echo OK: Upload data\etf_prices.csv.gz data\etf_codes.csv data\snapshot_manifest.json to GitHub.
pause
