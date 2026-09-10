@echo off
echo ===================================================
echo Setting up Whisper Transcription Tool on Windows...
echo ===================================================

:: 1. Check if Python is installed on system
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH!
    echo Please install Python 3.10 or higher from python.org and check "Add Python to PATH".
    pause
    exit /b 1
)

:: 2. Create virtual environment
if not exist .venv (
    echo Creating fresh Python virtual environment in .venv...
    python -m venv .venv
)

:: 3. Install required libraries
echo Installing libraries from requirements.txt...
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

echo.
echo ===================================================
echo SETUP COMPLETE! You are ready to transcribe.
echo.
echo To see your videos, run:
echo   .\.venv\Scripts\python transcribe.py --list
echo.
echo To transcribe video #1, run:
echo   .\.venv\Scripts\python transcribe.py 1
echo ===================================================
pause
