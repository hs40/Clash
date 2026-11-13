@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

set "PLATFORM=%~1"
set "BACKUP=%~2"
if not defined PLATFORM (
    set /p "PLATFORM=平台（windows 或 openclash）："
)
if not defined BACKUP (
    set /p "BACKUP=备份目录路径："
)
if not defined PLATFORM (
    echo 未提供平台，已取消。
    pause
    exit /b 2
)
if not defined BACKUP (
    echo 未提供备份目录，已取消。
    pause
    exit /b 2
)

.venv\Scripts\python.exe scripts\platform.py rollback --platform "%PLATFORM%" --backup-dir "%BACKUP%"
set "RC=%ERRORLEVEL%"
echo.
if not "%RC%"=="0" echo 回滚未成功，退出码 %RC%；请查看上方信息。
pause
exit /b %RC%
