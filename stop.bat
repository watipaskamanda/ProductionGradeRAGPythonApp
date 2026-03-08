@echo off
echo Stopping RAG Application...
echo.

REM Kill Python processes
echo Stopping API and Streamlit...
taskkill /F /FI "WINDOWTITLE eq RAG API*" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq Streamlit UI*" >nul 2>&1

REM Kill Docker Qdrant
echo Stopping Qdrant...
taskkill /F /FI "WINDOWTITLE eq Qdrant*" >nul 2>&1
docker stop $(docker ps -q --filter ancestor=qdrant/qdrant) >nul 2>&1

echo.
echo RAG Application Stopped!
echo.
pause
