@echo off
setlocal
cd /d "%~dp0"
py -3.12 -m pip install -r requirements.txt
if errorlevel 1 exit /b 1
py -3.12 -m streamlit run app.py
