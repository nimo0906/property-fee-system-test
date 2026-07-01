@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo Starting Property Fee System in Windows server mode...
echo.

if "%PM_PORT%"=="" set "PM_PORT=5001"
if "%PM_HOST%"=="" set "PM_HOST=0.0.0.0"
if "%PM_DATA_DIR%"=="" set "PM_DATA_DIR=D:\PropertyFeeSystemData"
if "%PM_DB_PATH%"=="" set "PM_DB_PATH=%PM_DATA_DIR%\database\property.db"
if "%PM_BACKUP_DIR%"=="" set "PM_BACKUP_DIR=%PM_DATA_DIR%\backups"

if not exist "%PM_DATA_DIR%\database" mkdir "%PM_DATA_DIR%\database"
if not exist "%PM_BACKUP_DIR%" mkdir "%PM_BACKUP_DIR%"

echo Host: %PM_HOST%
echo Port: %PM_PORT%
echo Database: %PM_DB_PATH%
echo Backups: %PM_BACKUP_DIR%
echo.
echo Other computers should open:
echo   http://SERVER_IP:%PM_PORT%
echo.
echo Keep this window open while the system is in use.
echo.

if exist "PropertyFeeSystem\PropertyFeeSystem.exe" (
    "PropertyFeeSystem\PropertyFeeSystem.exe" --serve-only --port %PM_PORT%
) else (
    where py >nul 2>nul
    if %errorlevel%==0 (
        set "PYTHON_CMD=py -3"
    ) else (
        where python >nul 2>nul
        if %errorlevel%==0 (
            set "PYTHON_CMD=python"
        ) else (
            echo Python 3 was not found.
            echo Please install Python 3, then run install_windows_dependencies.bat.
            pause
            exit /b 1
        )
    )
    %PYTHON_CMD% desktop_app.py --serve-only --port %PM_PORT%
)

if errorlevel 1 (
    echo.
    echo Server startup failed.
    echo Please run diagnose_windows.bat and check the startup error log.
    pause
    exit /b 1
)
