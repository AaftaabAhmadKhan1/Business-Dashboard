@echo off
REM Quick Start Script for Batch Enrollment Dashboard

echo ================================================
echo   Batch Enrollment Dashboard
echo   Starting server...
echo ================================================

REM Check if dependencies are installed
python -c "import dash" 2>NUL
if errorlevel 1 (
    echo.
    echo Installing dependencies...
    pip install -r requirements_dashboard.txt
    echo.
)

REM Run the dashboard
echo.
echo Dashboard starting at http://localhost:8050
echo Press Ctrl+C to stop the server
echo.
python dashboard_app.py

pause
