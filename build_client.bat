@echo off
echo Building Remote Desktop Monitoring Client...
echo.

REM Install PyInstaller if not already installed
python -m pip install pyinstaller

REM Build the executable
pyinstaller --onefile --windowed --name "MonitoringAgent" --icon=icon.ico client/agent.py

echo.
echo Build complete!
echo Executable location: dist\MonitoringAgent.exe
echo.
pause
