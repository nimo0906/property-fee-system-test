@echo off
setlocal EnableExtensions
cd /d "%~dp0"
echo This entry now uses PACK_WINDOWS_RELEASE.bat.
echo.
call PACK_WINDOWS_RELEASE.bat
exit /b %errorlevel%
