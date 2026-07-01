@echo off
chcp 65001 >nul
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

set "LOG=windows_packaging.log"
echo ================================================== > "%LOG%"
echo Windows packaging started at %DATE% %TIME% >> "%LOG%"
echo Folder: %CD% >> "%LOG%"
echo ================================================== >> "%LOG%"
echo.
echo 正在打包 Windows 交付包，请不要关闭窗口。
echo 详细日志会写入：%CD%\%LOG%
echo.

call :log_step "检查当前目录"
if not exist "desktop_app.py" (
    echo [失败] 当前目录不对：没有 desktop_app.py
    echo [FAIL] missing desktop_app.py >> "%LOG%"
    goto :fail
)

call :log_step "检查 Python"
where py >> "%LOG%" 2>&1
if %errorlevel%==0 (
    set "PYTHON_CMD=py -3"
) else (
    where python >> "%LOG%" 2>&1
    if %errorlevel%==0 (
        set "PYTHON_CMD=python"
    ) else (
        echo [失败] 没找到 Python。请安装 Python 3，并勾选 Add python.exe to PATH。
        echo [FAIL] Python not found >> "%LOG%"
        goto :fail
    )
)
%PYTHON_CMD% --version >> "%LOG%" 2>&1
echo 使用 Python：%PYTHON_CMD%

call :log_step "运行打包前检查"
set "CI=1"
call check_windows_packaging_ready.bat >> "%LOG%" 2>&1
if errorlevel 1 (
    set "CI="
    echo [失败] 打包前检查未通过，详情看 %LOG%
    goto :fail
)

call :log_step "运行正式打包脚本"
call package_windows_release.bat >> "%LOG%" 2>&1
set "CI="
if errorlevel 1 (
    echo [失败] 正式打包失败，详情看 %LOG%
    goto :fail
)

if exist "release\windows\物业管理收费系统-v2.0-windows-server.zip" (
    echo.
    echo [成功] Windows 交付 zip 已生成：
    echo %CD%\release\windows\物业管理收费系统-v2.0-windows-server.zip
    echo [OK] zip generated >> "%LOG%"
    goto :done
)

echo [失败] 脚本结束了，但没有找到最终 zip。
echo [FAIL] zip not found >> "%LOG%"
goto :fail

:log_step
echo.
echo == %~1 ==
echo == %~1 == >> "%LOG%"
exit /b 0

:fail
echo.
echo 请把这个日志文件发回排查：
echo %CD%\%LOG%
echo.
pause
exit /b 1

:done
echo.
echo 可以把上面的 zip 发给用户。
echo.
pause
exit /b 0
