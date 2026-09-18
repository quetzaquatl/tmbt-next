@echo off
setlocal
title TMBT Next Beta
cd /d "%~dp0"
if not defined TMBT_WORKSPACE set "TMBT_WORKSPACE=D:\Projekt model\Trading_Model_Backtest_Studio_WORKSPACE"
set "TMBT_NEXT_PORT=8510"

echo.
echo =========================================
echo TMBT NEXT BETA 0.9.30 GIT WINDOW FIX
echo =========================================
echo Workspace: %TMBT_WORKSPACE%
echo URL: http://127.0.0.1:%TMBT_NEXT_PORT%
echo Active/Monitor card click force-opens Setup Inspector and criteria.
echo Feed Guardian auto-starts and repairs the existing Twelve collector when possible.
echo Entry context: symmetric NQ/ES SMT -^> PO3 -^> Asia/Midnight -^> iFVG.
echo Trade management: raw opposite SMT warns/takes partial; confirmed opposite SMT triggers exit review.
echo.

rem Defensive cleanup: older builds could leave an old server bound to 8510.
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /R /C:":%TMBT_NEXT_PORT% .*LISTENING"') do (
  echo Found stale TMBT Next listener PID %%P - stopping it ...
  taskkill /PID %%P /T /F >nul 2>&1
)
del /q next_ui.pid >nul 2>&1
timeout /t 1 /nobreak >nul

start "" "http://127.0.0.1:%TMBT_NEXT_PORT%/?v=0930"
py -3 server_boot.py
if errorlevel 1 python server_boot.py
pause