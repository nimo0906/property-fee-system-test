@echo off
chcp 65001 >nul
setlocal
set "APP_DATA_DIR=%APPDATA%\PropertyFeeSystemData"
set "ARCHIVE_ROOT=%USERPROFILE%\Desktop\PropertyFeeSystemDataBackups"
for /f "tokens=1-4 delims=/ " %%a in ("%date%") do set "DATE_PART=%%a%%b%%c%%d"
for /f "tokens=1-3 delims=:., " %%a in ("%time%") do set "TIME_PART=%%a%%b%%c"
set "TIME_PART=%TIME_PART: =0%"
set "ARCHIVE_DIR=%ARCHIVE_ROOT%\PropertyFeeSystem_before_reset_%DATE_PART%_%TIME_PART%"

echo Property Billing System trial data reset
echo WARNING: This script is only for trial/demo data.
echo WARNING: If this Windows user contains real business data, close this window now.
echo.
set /p CONFIRM=Type RESET and press Enter to continue: 
if not "%CONFIRM%"=="RESET" (
    echo Cancelled. No data was changed.
    pause
    exit /b 0
)
echo Data directory: %APP_DATA_DIR%
echo Backup target: %ARCHIVE_DIR%
echo.

if not exist "%APP_DATA_DIR%" (
    echo No existing data directory found. Nothing to reset.
    echo.
    pause
    exit /b 0
)

mkdir "%ARCHIVE_ROOT%" >nul 2>nul
xcopy "%APP_DATA_DIR%" "%ARCHIVE_DIR%\" /E /I /H /Y >nul
if errorlevel 1 (
    echo Backup failed. Data was not reset.
    echo Please copy this window content to support.
    pause
    exit /b 1
)

rmdir /S /Q "%APP_DATA_DIR%"
if exist "%APP_DATA_DIR%" (
    echo Reset failed. Please close PropertyBillingSystem.exe and try again.
    pause
    exit /b 1
)

echo Existing data has been backed up and reset.
echo Backup saved at: %ARCHIVE_DIR%
echo Start PropertyBillingSystem.exe again to create a clean trial database.
echo.
pause
