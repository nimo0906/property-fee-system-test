@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo Building Windows desktop package...

where py >nul 2>nul
if %errorlevel%==0 (
    set "PYTHON_CMD=py -3"
) else (
    where python >nul 2>nul
    if %errorlevel%==0 (
        set "PYTHON_CMD=python"
    ) else (
        echo Python 3 was not found.
        pause
        exit /b 1
    )
)

%PYTHON_CMD% -m pip install --upgrade pip
%PYTHON_CMD% -m pip install -r requirements.txt pyinstaller
if errorlevel 1 (
    echo Dependency installation failed.
    pause
    exit /b 1
)

%PYTHON_CMD% -m PyInstaller --clean --noconfirm property_fee_system.spec
if errorlevel 1 (
    echo Build failed.
    pause
    exit /b 1
)

echo.
echo Build completed: dist\PropertyFeeSystem\PropertyFeeSystem.exe
echo Included user docs: 用户快速开始.md, Windows客户试用说明.md, 交付验收清单.md, 使用说明.md
echo For a customer-ready zip, run package_windows_release.bat after this build succeeds.
pause
