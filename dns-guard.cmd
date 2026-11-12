@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "ACTION=--apply"
if /I "%~1"=="check" set "ACTION=--check"
if /I "%~1"=="--check" set "ACTION=--check"
if /I "%~1"=="remove" set "ACTION=--remove"
if /I "%~1"=="--remove" set "ACTION=--remove"

if /I not "%ACTION%"=="--check" (
  net session >nul 2>&1
  if errorlevel 1 (
    echo Requesting administrator privileges...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -ArgumentList '%ACTION%' -Verb RunAs"
    exit /b
  )
)

".venv\Scripts\python.exe" "scripts\dns_guard.py" %ACTION%
set "CODE=%ERRORLEVEL%"
echo.
echo Exit code: %CODE%
pause
exit /b %CODE%
