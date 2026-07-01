@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "LOG=windows_env_check.log"
echo Windows env check > "%LOG%"
echo Date: %DATE% %TIME% >> "%LOG%"
echo Folder: %CD% >> "%LOG%"
echo. >> "%LOG%"

echo Checking environment...

echo == files == >> "%LOG%"
dir /b >> "%LOG%" 2>&1

echo. >> "%LOG%"
echo == python == >> "%LOG%"
where py >> "%LOG%" 2>&1
where python >> "%LOG%" 2>&1
py -3 --version >> "%LOG%" 2>&1
python --version >> "%LOG%" 2>&1

echo. >> "%LOG%"
echo == powershell == >> "%LOG%"
where powershell >> "%LOG%" 2>&1
powershell -NoProfile -Command "$PSVersionTable.PSVersion" >> "%LOG%" 2>&1

echo. >> "%LOG%"
echo == required == >> "%LOG%"
for %%F in (desktop_app.py desktop_runtime.py server.py requirements.txt property_fee_system.spec PACK_WINDOWS_RELEASE.bat USER_GUIDE_WINDOWS.txt start_windows.bat start_windows_server.bat diagnose_windows.bat) do (
  if exist "%%F" (echo PASS %%F >> "%LOG%") else (echo FAIL %%F >> "%LOG%")
)

echo Done. Send this log back if packaging still fails:
echo %CD%\%LOG%
pause
