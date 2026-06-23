@echo off
chcp 65001 >nul
setlocal

set "TASK_NAME=PropertyFeeSystemServer"

net session >nul 2>nul
if errorlevel 1 (
    echo This script must be run as administrator.
    echo Right-click this file and choose: Run as administrator.
    pause
    exit /b 1
)

echo Stopping and deleting Windows background task: %TASK_NAME%
schtasks /End /TN "%TASK_NAME%" >nul 2>nul
schtasks /Delete /TN "%TASK_NAME%" /F
if errorlevel 1 (
    echo Failed to delete task, or task does not exist.
    pause
    exit /b 1
)

echo Deleted.
echo Data was not deleted. Data remains in D:\PropertyFeeSystemData
pause
