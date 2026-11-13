@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

whoami /groups | findstr /C:"S-1-16-12288" /C:"S-1-16-16384" >nul 2>&1
if errorlevel 1 (
    echo Requesting administrator privileges...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

echo SHELL integrity:
whoami /groups | findstr /C:"S-1-16"
echo PYTHON integrity:
.venv\Scripts\python.exe -c "import subprocess,sys; t=subprocess.run(['whoami','/groups'],capture_output=True,text=True,encoding='utf-8',errors='replace').stdout; print([l for l in t.splitlines() if 'S-1-16' in l]); sys.exit(0 if ('S-1-16-12288' in t or 'S-1-16-16384' in t) else 3)"
if errorlevel 1 (
    echo Python is not elevated - Low or Medium integrity. Stopped; no files written.
    echo Approve UAC and run this script in the new administrator window.
    pause
    exit /b 1
)

.venv\Scripts\python.exe scripts\platform.py deploy --platform windows --apply
set "RC=%ERRORLEVEL%"
echo.
if not "%RC%"=="0" echo Deploy failed with exit code %RC%. See report above.
pause
exit /b %RC%
