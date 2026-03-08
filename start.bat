@echo off
echo Starting RAG Application...
echo.

REM Start PostgreSQL Test DB
echo [1/4] Starting PostgreSQL Test Database...
docker start paymaart-test-db 2>nul || docker run --name paymaart-test-db -e POSTGRES_PASSWORD=testpass -e POSTGRES_DB=paymaart_test -p 5432:5432 -d postgres:15
timeout /t 3 /nobreak >nul

REM Start Qdrant in a new window
echo [2/4] Starting Qdrant Vector Database...
start "Qdrant" cmd /k "docker run -p 6333:6333 qdrant/qdrant"
timeout /t 5 /nobreak >nul

REM Start API in a new window
echo [3/4] Starting FastAPI Backend...
start "RAG API" cmd /k "cd /d %~dp0 && py -3.13 -m uvicorn api:app --host 0.0.0.0 --port 8000 --reload"
timeout /t 3 /nobreak >nul

REM Start Streamlit Chat UI in a new window
echo [4/4] Starting Streamlit Chat UI...
start "Streamlit Chat" cmd /k "cd /d %~dp0 && py -3.13 -m streamlit run chat_app.py"

echo.
echo ========================================
echo RAG Application Started!
echo ========================================
echo.
echo PostgreSQL: localhost:5432
echo Qdrant:     http://localhost:6333
echo API Docs:   http://localhost:8000/docs
echo Streamlit Chat: http://localhost:8501
echo.
echo Press any key to close this window...
pause >nul
