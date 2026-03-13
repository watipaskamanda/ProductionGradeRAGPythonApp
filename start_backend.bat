@echo off
echo Starting Enterprise RAG Backend...
echo =====================================

REM Activate virtual environment
if exist ".venv\Scripts\activate.bat" (
    echo Activating virtual environment...
    call .venv\Scripts\activate.bat
) else if exist ".venv1\Scripts\activate.bat" (
    echo Activating virtual environment...
    call .venv1\Scripts\activate.bat
) else (
    echo Warning: No virtual environment found
)

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python not found
    pause
    exit /b 1
)

REM Install dependencies if needed
if not exist "requirements.txt" (
    echo Warning: requirements.txt not found
) else (
    echo Installing/updating dependencies...
    pip install -r requirements.txt
)

REM Start the backend
echo.
echo Starting FastAPI backend on http://localhost:8000
echo API docs will be available at http://localhost:8000/docs
echo Press Ctrl+C to stop the server
echo.

python start_backend.py

pause