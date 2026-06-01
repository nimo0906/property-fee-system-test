@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo Starting Property Fee System...

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
        echo Please install Python 3, then run install_windows_dependencies.bat.
        pause
        exit /b 1
    )
)

%PYTHON_CMD% desktop_app.py

if errorlevel 1 (
    echo.
    echo Startup failed.
    echo Please run diagnose_windows.bat and send the displayed information to support.
    echo You can also run install_windows_dependencies.bat, then try again.
    pause
    exit /b 1
)
