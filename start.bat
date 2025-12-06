@echo off
REM Srimad-Bhagavatam Verse Finder - Quick Start Script for Windows

echo ====================================
echo Srimad-Bhagavatam Verse Finder
echo ====================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed. Please install Python 3.7 or higher.
    pause
    exit /b 1
)

echo [OK] Python found
echo.

REM Install dependencies
echo [INFO] Installing dependencies...
pip install -r requirements.txt

if errorlevel 1 (
    echo [ERROR] Failed to install dependencies
    pause
    exit /b 1
)

echo [OK] Dependencies installed successfully
echo.

REM Ask user which mode to run
echo Choose mode:
echo 1. Web App (Browser-based UI)
echo 2. CLI (Command-line interface)
echo.
set /p choice="Enter choice (1 or 2): "

if "%choice%"=="1" (
    echo.
    echo [INFO] Starting web server...
    echo [INFO] Open your browser and go to: http://localhost:5000
    echo [INFO] Press Ctrl+C to stop the server
    echo.
    python app.py
) else if "%choice%"=="2" (
    echo.
    set /p canto="Enter Canto (1-12): "
    set /p chapter="Enter Chapter: "
    set /p verse="Enter Verse: "
    echo.
    python fetch_verse_cli.py %canto% %chapter% %verse%
    pause
) else (
    echo [ERROR] Invalid choice
    pause
    exit /b 1
)
