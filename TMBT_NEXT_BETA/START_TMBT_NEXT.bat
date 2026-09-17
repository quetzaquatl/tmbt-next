@echo off
setlocal
title TMBT Next Beta
cd /d "%~dp0"
if not defined TMBT_WORKSPACE set "TMBT_WORKSPACE=D:\Projekt model\Trading_Model_Backtest_Studio_WORKSPACE"
set "TMBT_NEXT_PORT=8510"

echo.
echo =========================================
echo TMBT NEXT BETA 0.9.16 HTF GATE
echo =========================================
echo Workspace: %TMBT_WORKSPACE%
echo URL: http://127.0.0.1:%TMBT_NEXT_PORT%
echo Active tab: only fresh, in-session actionable models.
echo Monitor tab: background / wait / idle / expired / proxy / stale.
echo Notifications: persistent local history for model, research and system alerts.
echo HTF filter: iFVG requires closed 1H EMA20/50 directional alignment.
echo HTF safety: opposite direction, neutral or stale HTF blocks the iFVG setup.
echo EBP matrix: NQ / ES x 15m / 30m / 1H
echo Closed-bar evaluator active; 4-bar retest window; 2R target.
echo Feed priority: true NQ/ES futures mirror -^> QQQ/SPY monitoring-only fallback.
echo Safety: proxy or stale feeds cannot fire live alerts.
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
