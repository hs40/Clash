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

rem Prefer the base interpreter recorded in pyvenv.cfg. This script only uses
rem the standard library, and the base interpreter has proven reliable when elevated.
set "PYTHON=.venv\Scripts\python.exe"
if exist ".venv\pyvenv.cfg" (
  for /f "usebackq tokens=1,* delims== " %%A in (".venv\pyvenv.cfg") do (
    if /I "%%A"=="home" set "PYHOME=%%B"
  )
)
if defined PYHOME if exist "%PYHOME%\python.exe" set "PYTHON=%PYHOME%\python.exe"
"%PYTHON%" "scripts\dns_guard.py" %ACTION%
set "CODE=%ERRORLEVEL%"
echo.
echo Exit code: %CODE%
pause
exit /b %CODE%
