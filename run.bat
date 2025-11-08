@echo off
REM Quick start script for Optimization Agent - Windows Version
echo ========================================
echo   Starting Optimization AI
echo ========================================
echo.

REM Check if virtual environment exists
if not exist Tolis_Env (
    echo ERROR: Virtual environment not found!
    echo Please run setup.bat first
    pause
    exit /b 1
)

REM Check if Ollama is running
echo Checking if Ollama is running...
curl -s http://localhost:11434/api/tags >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo WARNING: Ollama doesn't seem to be running!
    echo.
    echo Please start Ollama first:
    echo 1. Open Ollama application, or
    echo 2. Run 'ollama serve' in another terminal
    echo.
    echo Press any key to continue anyway, or Ctrl+C to exit...
    pause >nul
)

echo.
echo Starting server...
echo.
echo The server will start at: http://localhost:8000
echo.
echo Press Ctrl+C to stop the server
echo ========================================
echo.

REM Activate virtual environment and start server
call Tolis_Env\Scripts\activate.bat
uvicorn api:app --reload --host 0.0.0.0 --port 8000
