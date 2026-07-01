@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"

set "TASK_NAME=PropertyFeeSystemServer"
set "PM_PORT=5001"
set "PM_HOST=0.0.0.0"
set "PM_DATA_DIR=D:\PropertyFeeSystemData"
set "PM_DB_PATH=%PM_DATA_DIR%\database\property.db"
set "PM_BACKUP_DIR=%PM_DATA_DIR%\backups"
set "PM_LOG_DIR=%PM_DATA_DIR%\logs"
set "EXE_PATH=%~dp0PropertyFeeSystem\PropertyFeeSystem.exe"
set "RUNNER_PATH=%PM_DATA_DIR%\run_server_background.cmd"

net session >nul 2>nul
if errorlevel 1 (
    echo This script must be run as administrator.
    echo Right-click this file and choose: Run as administrator.
    pause
    exit /b 1
)

if not exist "%EXE_PATH%" (
    echo Missing executable: %EXE_PATH%
    echo Put this script in the released folder that contains PropertyFeeSystem\PropertyFeeSystem.exe.
    pause
    exit /b 1
)

if not exist "%PM_DATA_DIR%\database" mkdir "%PM_DATA_DIR%\database"
if not exist "%PM_BACKUP_DIR%" mkdir "%PM_BACKUP_DIR%"
if not exist "%PM_LOG_DIR%" mkdir "%PM_LOG_DIR%"

> "%RUNNER_PATH%" echo @echo off
>> "%RUNNER_PATH%" echo chcp 65001 ^>nul
>> "%RUNNER_PATH%" echo set "PM_HOST=%PM_HOST%"
>> "%RUNNER_PATH%" echo set "PM_PORT=%PM_PORT%"
>> "%RUNNER_PATH%" echo set "PM_DATA_DIR=%PM_DATA_DIR%"
>> "%RUNNER_PATH%" echo set "PM_DB_PATH=%PM_DB_PATH%"
>> "%RUNNER_PATH%" echo set "PM_BACKUP_DIR=%PM_BACKUP_DIR%"
>> "%RUNNER_PATH%" echo set "PM_LOG_DIR=%PM_LOG_DIR%"
>> "%RUNNER_PATH%" echo cd /d "%~dp0"
>> "%RUNNER_PATH%" echo "%EXE_PATH%" --serve-only --port %PM_PORT% ^>^> "%PM_LOG_DIR%\server_task.log" 2^>^&1

echo Installing Windows background startup task...
echo Task: %TASK_NAME%
echo Host: %PM_HOST%
echo Port: %PM_PORT%
echo Data: %PM_DATA_DIR%
echo Runner: %RUNNER_PATH%
echo.

schtasks /Create /TN "%TASK_NAME%" /SC ONSTART /RU SYSTEM /RL HIGHEST /TR "\"%RUNNER_PATH%\"" /F
if errorlevel 1 (
    echo Failed to create scheduled task.
    pause
    exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -Command "if (-not (Get-NetFirewallRule -DisplayName 'Property Fee System 5001' -ErrorAction SilentlyContinue)) { New-NetFirewallRule -DisplayName 'Property Fee System 5001' -Direction Inbound -Action Allow -Protocol TCP -LocalPort %PM_PORT% | Out-Null }"
if errorlevel 1 (
    echo Firewall rule creation failed. You can still add TCP port %PM_PORT% manually in Windows Firewall.
)

schtasks /Run /TN "%TASK_NAME%"
if errorlevel 1 (
    echo Task was installed, but immediate start failed. Restart the server or run status_windows_background_task.bat.
    pause
    exit /b 1
)

echo.
echo Installed and started.
echo Employees can open: http://SERVER_IP:%PM_PORT%
echo Data directory: %PM_DATA_DIR%
echo Log file: %PM_LOG_DIR%\server_task.log
echo.
pause
