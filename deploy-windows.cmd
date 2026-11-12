@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

net session >nul 2>&1
if errorlevel 1 (
    echo 正在请求管理员权限……
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

.venv\Scripts\python.exe scripts\platform.py deploy --platform windows --apply
set "RC=%ERRORLEVEL%"
echo.
if not "%RC%"=="0" echo 部署未成功，退出码 %RC%；请查看上方报告。
pause
exit /b %RC%
