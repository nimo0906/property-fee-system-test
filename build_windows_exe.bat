@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo Building Windows desktop executable...

echo Please use PACK_WINDOWS_RELEASE.bat for the customer-ready zip.
echo.

where py >nul 2>nul
if %errorlevel%==0 (
    set "PYTHON_CMD=py -3"
) else (
    where python >nul 2>nul
    if %errorlevel%==0 (
        set "PYTHON_CMD=python"
    ) else (
        echo Python 3 was not found.
        if not defined CI pause
        exit /b 1
    )
)

%PYTHON_CMD% -m pip install --upgrade pip
%PYTHON_CMD% -m pip install -r requirements.txt pyinstaller
if errorlevel 1 (
    echo Dependency installation failed.
    if not defined CI pause
    exit /b 1
)

%PYTHON_CMD% -m PyInstaller --clean --noconfirm property_fee_system.spec
if errorlevel 1 (
    echo Build failed.
    if not defined CI pause
    exit /b 1
)

echo.
echo Build completed: dist\PropertyFeeSystem\PropertyFeeSystem.exe
echo For a customer-ready zip, run PACK_WINDOWS_RELEASE.bat.
if not defined CI pause
