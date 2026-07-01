@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

set "LOG=windows_packaging.log"
set "RELEASE_ROOT=release\windows"
set "RELEASE_NAME=PropertyFeeSystem-windows-server"
set "RELEASE_DIR=%RELEASE_ROOT%\%RELEASE_NAME%"
set "ZIP_PATH=%RELEASE_ROOT%\%RELEASE_NAME%.zip"

echo ================================================== > "%LOG%"
echo PropertyFeeSystem Windows packaging >> "%LOG%"
echo Date: %DATE% %TIME% >> "%LOG%"
echo Folder: %CD% >> "%LOG%"
echo ================================================== >> "%LOG%"

echo PropertyFeeSystem Windows packaging
echo Log file: %CD%\%LOG%
echo.

if not exist "desktop_app.py" (
  echo FAIL: desktop_app.py not found. You are not in source folder.
  echo FAIL: desktop_app.py not found >> "%LOG%"
  goto :fail
)

call :need_file "desktop_runtime.py"
if errorlevel 1 goto :fail
call :need_file "server.py"
if errorlevel 1 goto :fail
call :need_file "requirements.txt"
if errorlevel 1 goto :fail
call :need_file "property_fee_system.spec"
if errorlevel 1 goto :fail
call :need_file "static\desktop-app-icon.ico"
if errorlevel 1 goto :fail
call :need_file "USER_GUIDE_WINDOWS.txt"
if errorlevel 1 goto :fail
call :need_file "start_windows.bat"
if errorlevel 1 goto :fail
call :need_file "start_windows_server.bat"
if errorlevel 1 goto :fail
call :need_file "diagnose_windows.bat"
if errorlevel 1 goto :fail

where py >> "%LOG%" 2>&1
if %errorlevel%==0 (
  set "PYTHON_CMD=py -3"
) else (
  where python >> "%LOG%" 2>&1
  if %errorlevel%==0 (
    set "PYTHON_CMD=python"
  ) else (
    echo FAIL: Python was not found. Install Python 3 and check Add python.exe to PATH.
    echo FAIL: Python not found >> "%LOG%"
    goto :fail
  )
)

%PYTHON_CMD% --version >> "%LOG%" 2>&1
if errorlevel 1 goto :fail

echo Installing dependencies...
%PYTHON_CMD% -m pip install --upgrade pip >> "%LOG%" 2>&1
if errorlevel 1 (
  echo FAIL: pip upgrade failed. See %LOG%
  goto :fail
)
%PYTHON_CMD% -m pip install -r requirements.txt pyinstaller >> "%LOG%" 2>&1
if errorlevel 1 (
  echo FAIL: dependency install failed. See %LOG%
  goto :fail
)

echo Building exe...
%PYTHON_CMD% -m PyInstaller --clean --noconfirm property_fee_system.spec >> "%LOG%" 2>&1
if errorlevel 1 (
  echo FAIL: PyInstaller build failed. See %LOG%
  goto :fail
)

if not exist "dist\PropertyFeeSystem\PropertyFeeSystem.exe" (
  echo FAIL: dist\PropertyFeeSystem\PropertyFeeSystem.exe not found.
  echo FAIL: exe missing >> "%LOG%"
  goto :fail
)

if exist "%RELEASE_DIR%" rmdir /S /Q "%RELEASE_DIR%" >> "%LOG%" 2>&1
if exist "%ZIP_PATH%" del /Q "%ZIP_PATH%" >> "%LOG%" 2>&1
if not exist "%RELEASE_ROOT%" mkdir "%RELEASE_ROOT%" >> "%LOG%" 2>&1
mkdir "%RELEASE_DIR%" >> "%LOG%" 2>&1
if errorlevel 1 (
  echo FAIL: create release folder failed. See %LOG%
  goto :fail
)

xcopy "dist\PropertyFeeSystem" "%RELEASE_DIR%\PropertyFeeSystem\" /E /I /H /Y >> "%LOG%" 2>&1
if errorlevel 1 (
  echo FAIL: copy dist folder failed. See %LOG%
  goto :fail
)

call :copy_required "USER_GUIDE_WINDOWS.txt"
if errorlevel 1 goto :fail
call :copy_required "diagnose_windows.bat"
if errorlevel 1 goto :fail
call :copy_required "start_windows.bat"
if errorlevel 1 goto :fail
call :copy_required "start_windows_server.bat"
if errorlevel 1 goto :fail
call :copy_if_exists "install_windows_background_task.bat"
call :copy_if_exists "status_windows_background_task.bat"
call :copy_if_exists "uninstall_windows_background_task.bat"
call :copy_if_exists "RESET_TRIAL_DATA.bat"

> "%RELEASE_DIR%\DELIVERY_RECORD.txt" echo PropertyFeeSystem Windows release
>> "%RELEASE_DIR%\DELIVERY_RECORD.txt" echo Date: %DATE% %TIME%
>> "%RELEASE_DIR%\DELIVERY_RECORD.txt" echo Entry: PropertyFeeSystem\PropertyFeeSystem.exe
>> "%RELEASE_DIR%\DELIVERY_RECORD.txt" echo Server entry: start_windows_server.bat
>> "%RELEASE_DIR%\DELIVERY_RECORD.txt" echo Data folder: %%APPDATA%%\PropertyFeeSystemData
>> "%RELEASE_DIR%\DELIVERY_RECORD.txt" echo Server data folder: D:\PropertyFeeSystemData

where powershell >> "%LOG%" 2>&1
if %errorlevel%==0 (
  powershell -NoProfile -ExecutionPolicy Bypass -Command "Compress-Archive -Path '%RELEASE_DIR%' -DestinationPath '%ZIP_PATH%' -Force" >> "%LOG%" 2>&1
  if errorlevel 1 (
    echo FAIL: PowerShell zip failed. See %LOG%
    goto :fail
  )
) else (
  echo WARN: powershell not found, using python zip >> "%LOG%"
  %PYTHON_CMD% -c "import shutil; shutil.make_archive(r'%RELEASE_ROOT%\%RELEASE_NAME%', 'zip', r'%RELEASE_ROOT%', r'%RELEASE_NAME%')" >> "%LOG%" 2>&1
  if errorlevel 1 (
    echo FAIL: python zip failed. See %LOG%
    goto :fail
  )
)

if not exist "%ZIP_PATH%" (
  echo FAIL: zip was not generated.
  goto :fail
)

%PYTHON_CMD% -c "import sys,zipfile,re; z=sys.argv[1]; rx=re.compile(r'(^|/)(\.env|property\.db[^/]*|[^/]+\.db(?:-wal|-shm)?|__pycache__|\.pytest_cache|logs|backups)(/|$)|\.log$|\.pyc$'); f=zipfile.ZipFile(z); bad=[n for n in f.namelist() if rx.search(n.replace(chr(92),'/'))]; non=[n for n in f.namelist() if any(ord(c)>127 for c in n)]; f.close(); print('forbidden files:', len(bad)); print('non-ascii names:', len(non)); sys.exit(1 if bad or non else 0)" "%ZIP_PATH%" >> "%LOG%" 2>&1
if errorlevel 1 (
  echo FAIL: forbidden or non-ASCII files found in zip. See %LOG%
  goto :fail
)

echo.
echo SUCCESS: zip generated:
echo %CD%\%ZIP_PATH%
echo SUCCESS >> "%LOG%"
goto :done

:need_file
if not exist "%~1" (
  echo FAIL: missing %~1
  echo FAIL: missing %~1 >> "%LOG%"
  exit /b 1
)
echo OK: %~1 >> "%LOG%"
exit /b 0

:copy_required
if not exist "%~1" (
  echo FAIL: missing release helper %~1
  echo FAIL: missing release helper %~1 >> "%LOG%"
  exit /b 1
)
copy /Y "%~1" "%RELEASE_DIR%\%~1" >> "%LOG%" 2>&1
if errorlevel 1 exit /b 1
exit /b 0

:copy_if_exists
if exist "%~1" copy /Y "%~1" "%RELEASE_DIR%\%~1" >> "%LOG%" 2>&1
exit /b 0

:fail
echo.
echo Packaging failed. Send this log file back:
echo %CD%\%LOG%
echo.
pause
exit /b 1

:done
echo.
echo Send the zip above to the customer.
echo.
pause
exit /b 0
