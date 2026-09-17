@echo off
setlocal
title TMBT Next Beta
cd /d "%~dp0"
if not defined TMBT_WORKSPACE set "TMBT_WORKSPACE=D:\Projekt model\Trading_Model_Backtest_Studio_WORKSPACE"
set "TMBT_NEXT_PORT=8510"

echo.
echo =========================================
echo TMBT NEXT BETA 0.9.19 SMT TRADE MANAGEMENT
echo =========================================
echo Workspace: %TMBT_WORKSPACE%
echo URL: http://127.0.0.1:%TMBT_NEXT_PORT%
echo Active: setup cards with semantic status and direction colors.
echo Monitor: background / wait / idle / expired / proxy / stale.
echo Secondary tools: Outcomes / Paper / System / Logs moved behind More.
echo Notifications: persistent local history for model, research and system alerts.
echo Entry context: symmetric NQ/ES SMT -^> PO3 -^> Asia/Midnight -^> iFVG.
echo Trade management: raw opposite SMT warns/takes partial; confirmed opposite SMT triggers exit review.
echo Existing SIGNAL trades are managed, not retroactively blocked.
echo EBP matrix: NQ / ES x 15m / 30m / 1H
echo Feed priority: true NQ/ES futures mirror -^> QQQ/SPY monitoring-only fallback.
echo Safety: proxy or stale feeds cannot fire live alerts.
echo Context endpoint: http://127.0.0.1:%TMBT_NEXT_PORT%/api/context
echo Preflight endpoint: http://127.0.0.1:%TMBT_NEXT_PORT%/api/preflight
echo.

rem Defensive cleanup: older builds could leave an old server bound to 8510.
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /R /C:":%TMBT_NEXT_PORT% .*LISTENING"') do (
  echo Found stale TMBT Next listener PID %%P - stopping it ...
  taskkill /PID %%P /T /F >nul 2>&1
)
del /q next_ui.pid >nul 2>&1
timeout /t 1 /nobreak >nul

start "" "http://127.0.0.1:%TMBT_NEXT_PORT%"
py -3 server_boot.py
if errorlevel 1 python server_boot.py
pause