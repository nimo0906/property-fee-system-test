@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo Property Billing System diagnostics
echo.

where py >nul 2>nul
if %errorlevel%==0 (
    py -3 desktop_app.py --diagnose
) else (
    where python >nul 2>nul
    if %errorlevel%==0 (
        python desktop_app.py --diagnose
    ) else (
        echo Python 3 was not found.
        echo Please install Python 3 from https://www.python.org/downloads/windows/
    )
)

echo.
pause
