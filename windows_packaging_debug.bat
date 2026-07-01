@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"

set "LOG=windows_packaging_debug.log"
echo Windows packaging debug at %DATE% %TIME% > "%LOG%"
echo Folder: %CD% >> "%LOG%"
echo. >> "%LOG%"

echo 正在检查 Windows 打包环境...
echo 结果会写入：%CD%\%LOG%
echo.

echo == folder files == >> "%LOG%"
dir /b >> "%LOG%" 2>&1

echo. >> "%LOG%"
echo == python lookup == >> "%LOG%"
where py >> "%LOG%" 2>&1
where python >> "%LOG%" 2>&1

echo. >> "%LOG%"
echo == python version == >> "%LOG%"
py -3 --version >> "%LOG%" 2>&1
python --version >> "%LOG%" 2>&1

echo. >> "%LOG%"
echo == powershell lookup == >> "%LOG%"
where powershell >> "%LOG%" 2>&1
powershell -NoProfile -Command "$PSVersionTable.PSVersion" >> "%LOG%" 2>&1

echo. >> "%LOG%"
echo == required files == >> "%LOG%"
for %%F in (
  desktop_app.py
  desktop_runtime.py
  server.py
  requirements.txt
  property_fee_system.spec
  check_windows_packaging_ready.bat
  package_windows_release.bat
  Windows客户试用说明.md
  用户快速开始.md
) do (
  if exist "%%F" (
    echo PASS %%F >> "%LOG%"
  ) else (
    echo FAIL missing %%F >> "%LOG%"
  )
)

echo 检查完成，请把这个日志发回：
echo %CD%\%LOG%
pause
