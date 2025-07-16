@echo off
echo ========================================
echo Finance Manager - Interactive Menu
echo ========================================
echo.

REM Run the menu program inside the running app container

docker-compose exec app python menu/main.py

echo.
echo ========================================
echo Menu session ended.
echo ========================================
pause 