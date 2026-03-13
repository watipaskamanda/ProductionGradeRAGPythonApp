@echo off
echo Installing Enterprise RAG Dependencies...
echo ========================================

REM Activate virtual environment
if exist ".venv\Scripts\activate.bat" (
    echo Activating virtual environment (.venv)...
    call .venv\Scripts\activate.bat
) else if exist ".venv1\Scripts\activate.bat" (
    echo Activating virtual environment (.venv1)...
    call .venv1\Scripts\activate.bat
) else (
    echo Warning: No virtual environment found
    echo Creating new virtual environment...
    python -m venv .venv
    call .venv\Scripts\activate.bat
)

REM Upgrade pip
echo Upgrading pip...
python -m pip install --upgrade pip

REM Install core dependencies first
echo Installing core dependencies...
pip install fastapi uvicorn python-dotenv pydantic

REM Install AI/ML dependencies
echo Installing AI/ML dependencies...
pip install groq sentence-transformers

REM Install database dependencies
echo Installing database dependencies...
pip install qdrant-client psycopg2-binary sqlalchemy

REM Install LlamaIndex (with error handling)
echo Installing LlamaIndex...
pip install llama-index-core llama-index-readers-file
pip install llama-index-embeddings-huggingface || echo "Warning: Could not install llama-index-embeddings-huggingface"

REM Install LangGraph (optional)
echo Installing LangGraph (optional)...
pip install langgraph langchain-core langchain-community || echo "Warning: Could not install LangGraph - agentic features will be disabled"

REM Install remaining dependencies
echo Installing remaining dependencies...
pip install streamlit python-multipart pymysql

echo.
echo ========================================
echo Installation completed!
echo ========================================
echo.
echo You can now start the backend with:
echo   python start_backend.py
echo.
echo Or use the batch file:
echo   start_backend.bat
echo.

pause