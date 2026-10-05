@echo off
cd /d "%~dp0"
py -3 run_viewer.py
if errorlevel 1 (
  echo If Python was not found, install Python 3 from https://www.python.org/downloads/
  echo Or try: python run_viewer.py
  pause
)
