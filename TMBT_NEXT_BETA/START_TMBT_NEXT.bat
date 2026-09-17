@echo off
setlocal
title TMBT Next Beta
cd /d "%~dp0"
if not defined TMBT_WORKSPACE set "TMBT_WORKSPACE=D:\Projekt model\Trading_Model_Backtest_Studio_WORKSPACE"
set "TMBT_NEXT_PORT=8510"
echo.
echo =========================================
echo TMBT NEXT BETA 0.9.14 ACTIVE DESK
echo =========================================
echo Workspace: %TMBT_WORKSPACE%
echo URL: http://127.0.0.1:%TMBT_NEXT_PORT%
echo Active tab: only fresh, in-session actionable models.
echo Monitor tab: background / wait / idle / expired / proxy / stale.
echo EBP matrix: NQ / ES x 15m / 30m / 1H
echo Closed-bar evaluator active; 4-bar retest window; 2R target.
echo Feed priority: true NQ/ES futures mirror -^> QQQ/SPY monitoring-only fallback.
echo Safety: proxy or stale feeds cannot fire live alerts.
echo Preflight endpoint: http://127.0.0.1:%TMBT_NEXT_PORT%/api/preflight
echo.
start "" "http://127.0.0.1:%TMBT_NEXT_PORT%"
py -3 server_boot.py
if errorlevel 1 python server_boot.py
pause
