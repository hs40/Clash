@echo off
setlocal
cd /d "%~dp0"

set "NODE_SOURCE=%~1"
if not defined NODE_SOURCE set "NODE_SOURCE=%CLASH_NODE_SOURCE%"
if not defined NODE_SOURCE (
    set /p "NODE_SOURCE=请输入节点来源 FIB profile 路径："
)
if not defined NODE_SOURCE (
    echo 未提供节点来源，已取消。
    pause
    exit /b 2
)

.venv\Scripts\python.exe scripts\platform.py deploy --platform openclash --apply --node-source "%NODE_SOURCE%"
set "RC=%ERRORLEVEL%"
echo.
if not "%RC%"=="0" echo 部署未成功，退出码 %RC%；请查看上方报告。
pause
exit /b %RC%
