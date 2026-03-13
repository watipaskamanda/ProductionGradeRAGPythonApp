@echo off
echo Fixing Virtual Environment and Dependencies...
echo =============================================

REM Step 1: Deactivate any active virtual environment
echo Step 1: Deactivating virtual environment...
deactivate 2>nul

REM Step 2: Remove corrupted virtual environment
echo Step 2: Removing corrupted virtual environment...
if exist ".venv" (
    echo Removing .venv directory...
    rmdir /s /q .venv
)

REM Step 3: Create fresh virtual environment
echo Step 3: Creating fresh virtual environment...
python -m venv .venv

REM Step 4: Activate virtual environment
echo Step 4: Activating virtual environment...
call .venv\Scripts\activate.bat

REM Step 5: Upgrade pip
echo Step 5: Upgrading pip...
python -m pip install --upgrade pip

REM Step 6: Install dependencies in stages
echo Step 6: Installing dependencies in stages...

echo Installing core FastAPI dependencies...
pip install fastapi uvicorn python-dotenv pydantic

echo Installing AI/ML dependencies...
pip install groq sentence-transformers

echo Installing database dependencies...
pip install qdrant-client psycopg2-binary "sqlalchemy>=2.0.0" pymysql

echo Installing LlamaIndex core...
pip install llama-index-core llama-index-readers-file

echo Installing optional LlamaIndex embeddings...
pip install llama-index-embeddings-huggingface || echo "Warning: llama-index-embeddings-huggingface failed"

echo Installing Streamlit...
pip install streamlit python-multipart

echo Installing optional LangGraph...
pip install langgraph langchain-core langchain-community || echo "Warning: LangGraph failed - agentic features will be disabled"

echo.
echo =============================================
echo Virtual environment setup completed!
echo =============================================
echo.
echo Testing the installation...
python test_installation.py

echo.
echo You can now start the backend with:
echo   python start_backend.py
echo.

pause