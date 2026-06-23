@echo off
chcp 65001 >nul
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

set "RELEASE_ROOT=release\windows"
set "RELEASE_NAME=物业管理收费系统-v2.0-windows-server"
set "RELEASE_DIR=%RELEASE_ROOT%\%RELEASE_NAME%"
set "ZIP_PATH=%RELEASE_ROOT%\%RELEASE_NAME%.zip"

echo Building Windows server-ready release package...
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
        echo Install Python 3 and select "Add python.exe to PATH".
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

if not exist "dist\PropertyFeeSystem\PropertyFeeSystem.exe" (
    echo Build output not found: dist\PropertyFeeSystem\PropertyFeeSystem.exe
    if not defined CI pause
    exit /b 1
)

if exist "%RELEASE_DIR%" rmdir /S /Q "%RELEASE_DIR%"
if exist "%ZIP_PATH%" del /Q "%ZIP_PATH%"
mkdir "%RELEASE_DIR%"

xcopy "dist\PropertyFeeSystem" "%RELEASE_DIR%\PropertyFeeSystem\" /E /I /H /Y >nul
copy /Y "用户快速开始.md" "%RELEASE_DIR%\用户快速开始.md" >nul
copy /Y "新手交付说明.md" "%RELEASE_DIR%\新手交付说明.md" >nul
copy /Y "Windows客户试用说明.md" "%RELEASE_DIR%\Windows客户试用说明.md" >nul
copy /Y "Windows打包操作步骤.md" "%RELEASE_DIR%\Windows打包操作步骤.md" >nul
copy /Y "Windows用户发送文案.md" "%RELEASE_DIR%\Windows用户发送文案.md" >nul
copy /Y "使用说明.md" "%RELEASE_DIR%\使用说明.md" >nul
copy /Y "交付验收清单.md" "%RELEASE_DIR%\交付验收清单.md" >nul
copy /Y "正式交付清单.md" "%RELEASE_DIR%\正式交付清单.md" >nul
copy /Y "数据备份说明.md" "%RELEASE_DIR%\数据备份说明.md" >nul
copy /Y "真实数据试运行保护方案.md" "%RELEASE_DIR%\真实数据试运行保护方案.md" >nul
copy /Y "真实数据导入前验收清单.md" "%RELEASE_DIR%\真实数据导入前验收清单.md" >nul
copy /Y "清空本机试用数据.bat" "%RELEASE_DIR%\清空本机试用数据.bat" >nul
copy /Y "diagnose_windows.bat" "%RELEASE_DIR%\diagnose_windows.bat" >nul
copy /Y "start_windows.bat" "%RELEASE_DIR%\start_windows.bat" >nul
copy /Y "start_windows_server.bat" "%RELEASE_DIR%\start_windows_server.bat" >nul
copy /Y "install_windows_background_task.bat" "%RELEASE_DIR%\install_windows_background_task.bat" >nul
copy /Y "status_windows_background_task.bat" "%RELEASE_DIR%\status_windows_background_task.bat" >nul
copy /Y "uninstall_windows_background_task.bat" "%RELEASE_DIR%\uninstall_windows_background_task.bat" >nul
copy /Y "Windows服务器无黑框运行说明.md" "%RELEASE_DIR%\Windows服务器无黑框运行说明.md" >nul
copy /Y "check_windows_packaging_ready.bat" "%RELEASE_DIR%\check_windows_packaging_ready.bat" >nul

for /f "delims=" %%i in ('git rev-parse --short HEAD 2^>nul') do set "COMMIT=%%i"
if not defined COMMIT set "COMMIT=unknown"
for /f "delims=" %%i in ('%PYTHON_CMD% --version 2^>^&1') do set "PY_VERSION=%%i"

> "%RELEASE_DIR%\本次交付记录.md" echo # 物业管理收费系统 v2.0 Windows 服务器可用版交付记录
>> "%RELEASE_DIR%\本次交付记录.md" echo.
>> "%RELEASE_DIR%\本次交付记录.md" echo - 交付包名称：%RELEASE_NAME%
>> "%RELEASE_DIR%\本次交付记录.md" echo - 当前 commit：%COMMIT%
>> "%RELEASE_DIR%\本次交付记录.md" echo - Python 版本：%PY_VERSION%
>> "%RELEASE_DIR%\本次交付记录.md" echo - 交付类型：Windows 服务器共享/内部试用包
>> "%RELEASE_DIR%\本次交付记录.md" echo - 普通桌面入口：PropertyFeeSystem\PropertyFeeSystem.exe
>> "%RELEASE_DIR%\本次交付记录.md" echo - 服务器数据目录：D:\PropertyFeeSystemData
>> "%RELEASE_DIR%\本次交付记录.md" echo - 说明：本交付包不包含本机 property.db、.env、backups 或缓存文件；服务器无黑框模式请使用 install_windows_background_task.bat。

where powershell >nul 2>nul
if errorlevel 1 (
    echo PowerShell was not found. Release folder is ready: %RELEASE_DIR%
    if not defined CI pause
    exit /b 0
)

powershell -NoProfile -ExecutionPolicy Bypass -Command "Compress-Archive -Path '%RELEASE_DIR%' -DestinationPath '%ZIP_PATH%' -Force; $bad = @(); Add-Type -AssemblyName System.IO.Compression.FileSystem; $zip = [IO.Compression.ZipFile]::OpenRead('%ZIP_PATH%'); foreach ($e in $zip.Entries) { if ($e.FullName -match '(^|/)(\.env|property\.db|[^/]*\.db|backups/|\.pytest_cache/|__pycache__/|.*\.log)$') { $bad += $e.FullName } }; $zip.Dispose(); if ($bad.Count -gt 0) { Write-Host 'Forbidden files found in zip:'; $bad; exit 1 }"
if errorlevel 1 (
    echo Zip creation failed. Release folder is ready: %RELEASE_DIR%
    if not defined CI pause
    exit /b 1
)

echo.
echo Windows release package is ready:
echo %ZIP_PATH%
echo.
echo Server use: unzip it on Windows Server, then run install_windows_background_task.bat as administrator.
if not defined CI pause
