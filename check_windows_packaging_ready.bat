@echo off
setlocal EnableExtensions
cd /d "%~dp0"
echo This entry now uses CHECK_WINDOWS_ENV.bat.
echo.
call CHECK_WINDOWS_ENV.bat
exit /b %errorlevel%
