@echo off
echo Setting up Test Database...
echo.

REM Start PostgreSQL in Docker
echo [1/3] Starting PostgreSQL...
docker run --name paymaart-test-db -e POSTGRES_PASSWORD=testpass -e POSTGRES_DB=paymaart_test -p 5432:5432 -d postgres:15

REM Wait for PostgreSQL to be ready
echo [2/3] Waiting for database to be ready...
timeout /t 10 /nobreak >nul

REM Load test data
echo [3/3] Loading test data...
docker exec -i paymaart-test-db psql -U postgres -d paymaart_test < test_data.sql

echo.
echo ========================================
echo Test Database Ready!
echo ========================================
echo.
echo Host: localhost
echo Port: 5432
echo Database: paymaart_test
echo User: postgres
echo Password: testpass
echo.
echo Update your .env file with these credentials
echo.
pause
