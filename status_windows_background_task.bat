@echo off
chcp 65001 >nul
setlocal

set "TASK_NAME=PropertyFeeSystemServer"
set "PM_PORT=5001"
set "PM_DATA_DIR=D:\PropertyFeeSystemData"

echo Windows background task status: %TASK_NAME%
echo.
schtasks /Query /TN "%TASK_NAME%" /V /FO LIST
if errorlevel 1 (
    echo.
    echo Task is not installed.
    pause
    exit /b 1
)

echo.
echo Checking local HTTP endpoint...
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $r = Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:%PM_PORT%/' -TimeoutSec 5; Write-Host ('PASS http://127.0.0.1:%PM_PORT%/ status ' + [int]$r.StatusCode) } catch { Write-Host ('FAIL http://127.0.0.1:%PM_PORT%/ ' + $_.Exception.Message); exit 1 }"

echo.
echo Employees should open: http://SERVER_IP:%PM_PORT%
echo Data directory: %PM_DATA_DIR%
echo Log file: %PM_DATA_DIR%\logs\server_task.log
echo.
pause
