@echo off
echo ========================================
echo Remote Desktop Monitoring - Build Script
echo ========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    pause
    exit /b 1
)

echo Installing dependencies...
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install dependencies
    pause
    exit /b 1
)
echo Dependencies installed successfully!
echo.

echo Building client executable...
python -m PyInstaller --onefile --console --name "MonitoringAgent" client/agent.py
if errorlevel 1 (
    echo ERROR: Failed to build executable
    pause
    exit /b 1
)
echo Client executable built successfully!
echo.

echo ========================================
echo BUILD COMPLETE!
echo ========================================
echo.
echo Executable location: dist\MonitoringAgent.exe
echo.
echo To run the client:
echo   cd dist
echo   MonitoringAgent.exe --server ws://your-server.com/ws --fps 10 --quality 50
echo.
pause
