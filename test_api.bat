@echo off
echo Testing API startup...
cd /d %~dp0
echo Current directory: %cd%
echo.
echo Testing Python version:
py -3.13 --version
echo.
echo Testing uvicorn:
py -3.13 -m uvicorn --version
echo.
echo Starting API (press Ctrl+C to stop):
py -3.13 -m uvicorn api:app --host 0.0.0.0 --port 8000 --reload
pause