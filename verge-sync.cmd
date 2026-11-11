@echo off
chcp 65001 >nul
setlocal
set "ROOT=%~dp0"
set "PY=%ROOT%.venv\Scripts\python.exe"
if not exist "%PY%" (
  echo [错误] 找不到 %PY%
  echo 请先在仓库根目录创建 .venv 并安装 requirements.txt。
  pause
  exit /b 2
)
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "TARGET=%~1"
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd-HHmmss"') do set "TS=%%i"
if "%TS%"=="" set "TS=manual"
set "BACKUP=%ROOT%.tmp_verge_apply_backup_%TS%"

echo ============================================================
echo Clash Verge 全局 MVP 同步
echo 仓库：%ROOT%
echo 备份：%BACKUP%
if "%TARGET%"=="" (
  echo 目标：当前 profile
) else (
  echo 目标：%TARGET%
)
echo ============================================================
echo 即将写入 Verge AppData 并重启 Verge；失败会自动回滚。
echo 请确认已关闭正在编辑的 Verge 配置窗口。
pause

if "%TARGET%"=="" (
  "%PY%" "%ROOT%scripts\verge_apply.py" --workdir "%ROOT%.tmp_verge_preflight" --apply --restart --backup-dir "%BACKUP%"
) else (
  "%PY%" "%ROOT%scripts\verge_apply.py" --workdir "%ROOT%.tmp_verge_preflight" --profile "%TARGET%" --apply --restart --backup-dir "%BACKUP%"
)
set "CODE=%ERRORLEVEL%"
echo.
if "%CODE%"=="0" (
  echo [完成] 已应用并校验通过。
) else (
  echo [失败] 退出码 %CODE%。若已自动回滚，请查看上方日志；不要删除备份目录。
)
echo.
pause
exit /b %CODE%
