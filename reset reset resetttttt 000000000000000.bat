@echo off
echo ===== Resetting Database =====
echo.

:: Check if Python is installed
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Python is not installed or not in PATH.
    echo Please install Python 3.8 or later and try again.
    pause
    exit /b 1
)

:: Install required packages if not already installed
echo Installing required packages...
pip install psycopg2-binary python-dotenv

:: Run the reset script
echo.
echo Starting database reset...
python -m app.db.drop_and_recreate_tables

:: Pause to see the output
pause
