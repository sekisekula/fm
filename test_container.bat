@echo off
echo ===== Testing Docker Container File Structure =====
echo.

:: Check if container is running
docker ps | findstr "fm-app-1" >nul
if %ERRORLEVEL% neq 0 (
    echo ERROR: Container fm-app-1 is not running.
    echo Please run 1.bat first to start the containers.
    pause
    exit /b 1
)

echo [1/3] Checking container file structure...
docker exec fm-app-1 ls -la /app

echo.
echo [2/3] Checking if menu directory exists...
docker exec fm-app-1 ls -la /app/menu

echo.
echo [3/3] Testing menu execution...
docker exec fm-app-1 python -c "import sys; print('Python path:', sys.path); import menu.main; print('Menu module imported successfully!')"

echo.
echo ===== Test completed =====
pause 