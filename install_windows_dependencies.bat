@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo Installing dependencies for Property Billing System...

where py >nul 2>nul
if %errorlevel%==0 (
    set "PYTHON_CMD=py -3"
) else (
    where python >nul 2>nul
    if %errorlevel%==0 (
        set "PYTHON_CMD=python"
    ) else (
        echo.
        echo Python 3 was not found.
        echo Please install Python 3 from https://www.python.org/downloads/windows/
        echo During installation, select "Add python.exe to PATH".
        pause
        exit /b 1
    )
)

%PYTHON_CMD% -m pip install --upgrade pip
%PYTHON_CMD% -m pip install -r requirements.txt

if errorlevel 1 (
    echo.
    echo Dependency installation failed. Please confirm Python 3 and pip are available.
    pause
    exit /b 1
)

echo.
echo Dependencies installed. You can double-click start_windows.bat to launch the system.
pause
