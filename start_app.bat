@echo off
echo ==========================================================
echo      Qwen Payslip Processor - Application Starter
echo ==========================================================
echo.
echo This script will start the entire Qwen Payslip Processor application:
echo  1. Ensure Docker container is running
echo  2. Start the backend server
echo  3. Start the frontend web interface
echo.

REM Check if Docker is running first
echo Checking Docker container status...
docker ps | findstr "27842/tcp" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Docker container is not running. Starting container management script...
    echo.
    call start_docker.bat
    
    REM Check if the container started successfully
    docker ps | findstr "27842/tcp" >nul 2>&1
    if %ERRORLEVEL% NEQ 0 (
        echo.
        echo ERROR: Docker container failed to start.
        echo Please run start_docker.bat separately and follow the instructions.
        echo.
        pause
        exit /b 1
    )
) else (
    echo Docker container is running.
)

echo.
echo Setting up Python environment...

REM Check for Python installation
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Python is not installed or not in your PATH.
    echo Please install Python 3.11+ from https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

REM Check for existing virtual environment in root directory
if exist .venv (
    echo Found existing virtual environment in root directory.
) else (
    echo Creating new virtual environment in root directory...
    python -m venv .venv
    if %ERRORLEVEL% NEQ 0 (
        echo WARNING: Failed to create virtual environment. Will use global Python.
    ) else (
        echo Virtual environment created successfully!
    )
)

REM Install root dependencies if venv exists
if exist .venv (
    echo Installing dependencies in the virtual environment...
    call .venv\Scripts\activate.bat
    pip install -r requirements.txt
    if %ERRORLEVEL% NEQ 0 (
        echo WARNING: Error installing dependencies in virtual environment.
    ) else (
        echo Dependencies installed successfully!
    )
    call deactivate
)

echo.
echo Starting the backend and frontend applications...

REM Start backend in new window
echo Starting backend server...
if exist .venv (
    start "Qwen Payslip Processor - Backend" cmd /k "cd %CD% && call .venv\Scripts\activate.bat && cd backend && pip install -r requirements.txt && python -m uvicorn app.main:app --reload --port 8000"
) else (
    start "Qwen Payslip Processor - Backend" cmd /k "cd backend && pip install -r requirements.txt && python -m uvicorn app.main:app --reload --port 8000"
)

REM Start frontend in new window
echo Starting frontend web interface...
if exist .venv (
    start "Qwen Payslip Processor - Frontend" cmd /k "cd %CD% && call .venv\Scripts\activate.bat && cd frontend && pip install -r requirements.txt && python app.py"
) else (
    start "Qwen Payslip Processor - Frontend" cmd /k "cd frontend && pip install -r requirements.txt && python app.py"
)

echo.
echo Application starting!
echo.
echo The web interface will open automatically in your browser.
echo If it doesn't open automatically, access it at: http://localhost:5173
echo.
echo Container logs can be viewed with: docker logs qwen-payslip-processor
echo.
echo To stop the application, close both terminal windows and run:
echo   docker stop qwen-payslip-processor
echo.

timeout /t 5
start http://localhost:5173

echo.
pause 