@echo off
setlocal
cd /d "%~dp0"
echo [USERM V1.5] Refresh 20 ETFs and SPY benchmark from local CPS2 (no iFinD API)
echo [EOD] NYSE calendar plus 90-minute close buffer; incomplete sessions excluded.
py -3.12 scripts\refresh_data.py --source "C:\code\DATA\US\data\cps2_adjusted"
if errorlevel 1 (
  echo.
  echo ERROR: Refresh FAILED. Do not upload old data. Check SPY source and 21/21 latest date.
  echo If SPY has multiple exchange codes use:
  echo py -3.12 scripts\refresh_data.py --source "C:\code\DATA\US\data\cps2_adjusted" --spy-symbol SPY.P
  pause
  exit /b 1
)
echo.
echo [2/2] Verify ETF / SPY alignment
py -3.12 scripts\verify_data.py
if errorlevel 1 (
 echo ERROR: Data alignment verification failed. Do not upload to GitHub.
 pause
 exit /b 1
)
echo.
echo SUCCESS: Upload ALL 4 updated files under data\ to GitHub main/data:
echo     etf_prices.csv.gz
echo     spy_prices.csv.gz
echo     etf_codes.csv
echo     snapshot_manifest.json
pause
