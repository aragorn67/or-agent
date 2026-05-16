@echo off
REM Setup script for Optimization Agent - Windows Version
echo ========================================
echo   Optimization AI Setup (Windows)
echo ========================================
echo.

REM Check Python installation
echo [1/4] Checking Python installation...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH
    echo.
    echo Please install Python 3.10 or higher from:
    echo https://www.python.org/downloads/
    echo.
    echo IMPORTANT: Check "Add Python to PATH" during installation!
    pause
    exit /b 1
)
python --version
echo Python found!
echo.

REM Create virtual environment
echo [2/4] Creating virtual environment 'Tolis_Env'...
if exist Tolis_Env (
    echo Virtual environment already exists. Skipping...
) else (
    python -m venv Tolis_Env
    if %errorlevel% neq 0 (
        echo ERROR: Failed to create virtual environment
        pause
        exit /b 1
    )
    echo Virtual environment created!
)
echo.

REM Activate virtual environment and install dependencies
echo [3/4] Installing Python packages (includes the HiGHS solver - no separate solver install needed)...
echo This may take a few minutes...
call Tolis_Env\Scripts\activate.bat
if %errorlevel% neq 0 (
    echo ERROR: Failed to activate virtual environment
    pause
    exit /b 1
)

pip install --upgrade pip
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo ERROR: Failed to install dependencies
    pause
    exit /b 1
)
echo Dependencies installed!
echo.

REM Check for Ollama
echo [4/4] Checking for Ollama...
where ollama >nul 2>&1
if %errorlevel% neq 0 (
    echo WARNING: Ollama not found!
    echo.
    echo Ollama is required to run the AI features.
    echo Please install it from: https://ollama.ai
    echo.
    echo After installing Ollama, run:
    echo   ollama pull qwen3:14b
    echo.
) else (
    echo Ollama found!
    echo.
    echo Checking for required model...
    ollama list | findstr "qwen3:14b" >nul 2>&1
    if %errorlevel% neq 0 (
        echo Model qwen3:14b not found. Downloading...
        echo This will download about 9.3GB - may take several minutes
        ollama pull qwen3:14b
    ) else (
        echo Model qwen3:14b already installed!
    )
)
echo.

REM Solver note: the HiGHS solver is installed automatically by pip
REM (the 'highspy' wheel in requirements.txt). No GLPK or manual
REM solver install / PATH setup is required on Windows anymore.

echo ========================================
echo   Setup Complete!
echo ========================================
echo.
echo Next steps:
echo 1. To start the server, run: run.bat
echo 2. Or manually:
echo    - Open command prompt in this folder
echo    - Run: Tolis_Env\Scripts\activate.bat
echo    - Run: uvicorn api:app --reload --host 0.0.0.0 --port 8000
echo    - Open browser to: http://localhost:8000
echo.
echo For help, see:
echo - deliverables\Run_on_Windows.pdf (setup, expected results, troubleshooting)
echo.
pause
