@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo Windows packaging readiness check
echo.

set "FAILED=0"

where py >nul 2>nul
if %errorlevel%==0 (
    set "PYTHON_CMD=py -3"
) else (
    where python >nul 2>nul
    if %errorlevel%==0 (
        set "PYTHON_CMD=python"
    ) else (
        echo FAIL Python 3 was not found.
        echo Install Python 3.10 or 3.11 and select "Add python.exe to PATH".
        set "FAILED=1"
    )
)

if not "%FAILED%"=="1" (
    %PYTHON_CMD% --version
    %PYTHON_CMD% -m pip --version >nul 2>nul
    if errorlevel 1 (
        echo FAIL pip is not available.
        set "FAILED=1"
    ) else (
        echo PASS pip is available.
    )
)

call :check_file "desktop_app.py"
call :check_file "desktop_runtime.py"
call :check_file "server.py"
call :check_file "requirements.txt"
call :check_file "property_fee_system.spec"
call :check_file "package_windows_release.bat"
call :check_file "build_windows_exe.bat"
call :check_file "diagnose_windows.bat"
call :check_file "Windows客户试用说明.md"
call :check_file "用户快速开始.md"
call :check_file "清空本机试用数据.bat"

findstr /C:"('property.db', '.')" property_fee_system.spec >nul 2>nul
if %errorlevel%==0 (
    echo FAIL property_fee_system.spec includes local property.db. Do not package local database.
    set "FAILED=1"
) else (
    echo PASS property_fee_system.spec does not include local property.db.
)

if exist ".env" (
    echo WARN .env exists in source folder. It must not be copied into release package.
) else (
    echo PASS .env not found in source folder.
)

if exist "property.db" (
    echo WARN property.db exists in source folder. Release script is configured not to package it.
) else (
    echo PASS property.db not found in source folder.
)

echo.
if "%FAILED%"=="1" (
    echo Check failed. Fix the FAIL items above before packaging.
    if not defined CI pause
    exit /b 1
)

echo All required Windows packaging files are ready.
echo Next step: double-click package_windows_release.bat
echo.
if not defined CI pause
exit /b 0

:check_file
if exist %~1 (
    echo PASS %~1
) else (
    echo FAIL missing %~1
    set "FAILED=1"
)
exit /b 0
