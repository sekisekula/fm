@echo off
cd /d "%~dp0"

:: Database configuration - must match 000 start.bat
set DB_HOST=db
set DB_PORT=5432
set DB_NAME=postgres
set DB_USER=postgres
set DB_PASSWORD=postgres

echo ===== Database Configuration =====
echo Host: %DB_HOST%
echo Port: %DB_PORT%
echo Database: %DB_NAME%
echo Username: %DB_USER%
echo.

setlocal enabledelayedexpansion

echo ===== Database Connection Test =====
echo.

echo [1/4] Checking if Docker is running...
docker info >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo ERROR: Docker is not running or not installed.
    echo Please start Docker Desktop and try again.
    pause
    exit /b 1
)

echo [2/4] Checking containers status...
set CONTAINER_RUNNING=0
docker ps --format "{{.Names}}" | findstr "fm_db_1" >nul && set CONTAINER_RUNNING=1

if %CONTAINER_RUNNING%==0 (
    echo Database container is not running.
    echo [3/4] Starting containers...
    call "000 start.bat"
    if %ERRORLEVEL% neq 0 (
        echo ERROR: Failed to start containers.
        pause
        exit /b 1
    )
) else (
    echo Database container is already running.
)

echo [4/4] Checking database connection...
timeout /t 5 /nobreak >nul

echo [4/6] Checking database connection...
echo Using connection: postgresql://%DB_USER%:*****@%DB_HOST%:%DB_PORT%/%DB_NAME%

(
echo SELECT 'Connection successful' AS message, version() AS version;
echo \q
) > check_db_query.sql

docker-compose --env-file .env exec -T db psql -U %DB_USER% -d %DB_NAME% -f /check_db_query.sql > db_test_output.txt 2>&1
del check_db_query.sql

findstr /C:"Connection successful" db_test_output.txt >nul
if %ERRORLEVEL% equ 0 (
    echo.
    echo SUCCESS: Successfully connected to PostgreSQL!
    type db_test_output.txt | findstr /v "^$" | findstr /v "^Time:"
) else (
    echo.
    echo ERROR: Failed to connect to PostgreSQL:
    type db_test_output.txt
    echo.
    echo Additional troubleshooting steps:
    echo 1. Check if PostgreSQL is running in the container:
    echo    docker-compose --env-file .env exec db pg_ctl status
    echo 2. Check PostgreSQL logs:
    echo    docker-compose --env-file .env logs db
    echo 3. Try to connect manually:
    echo    docker-compose --env-file .env exec db psql -U %DB_USER% -d %DB_NAME%
)

del db_test_output.txt >nul 2>&1

echo.
echo [5/6] Checking database tables...
(
echo \dt
) | docker-compose --env-file .env exec -T db psql -U %DB_USER% -d %DB_NAME% 2>&1 | findstr /V "^$" | findstr /V "List of relations" | findstr /V "^$" >nul
if %ERRORLEVEL% equ 0 (
    echo Database contains tables.
) else (
    echo WARNING: No tables found in the database.
)

echo.
echo [6/6] Database connection details:
echo "  Host: %DB_HOST%"
echo "  Port: %DB_PORT%"
echo "  Name: %DB_NAME%"
echo "  User: %DB_USER%"

echo.
echo ===== Test Complete =====
pause
