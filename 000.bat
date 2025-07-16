@echo off
echo ========================================
echo Finance Manager - Starting API Server
echo ========================================
echo.
echo This will start the Finance Manager API server in Docker.
echo The FastAPI server will be available at http://localhost:8000
echo.

docker-compose down

docker-compose build

REM Set environment variable for API mode
set APP_MODE=api

echo Starting containers in API mode...
docker-compose up -d

if errorlevel 1 (
    echo ERROR: Failed to start containers!
    pause
    exit /b 1
)

echo.
echo ========================================
echo Finance Manager API Server Started!
echo ========================================
echo.
echo API Server: http://localhost:8000
echo Upload Form: http://localhost:8000/upload-form/
echo.
echo To run the interactive menu, use: 111.bat
echo To stop the server, use: docker-compose down
echo.
pause 