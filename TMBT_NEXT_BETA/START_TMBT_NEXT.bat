@echo off
setlocal
title TMBT Next Beta
cd /d "%~dp0"
if not defined TMBT_WORKSPACE set "TMBT_WORKSPACE=D:\Projekt model\Trading_Model_Backtest_Studio_WORKSPACE"
set "TMBT_NEXT_PORT=8510"
echo.
echo =========================================
echo TMBT NEXT BETA 0.9.12 EBP MATRIX READY
echo =========================================
echo Workspace: %TMBT_WORKSPACE%
echo URL: http://127.0.0.1:%TMBT_NEXT_PORT%
echo EBP matrix: NQ / ES x 15m / 30m / 1H
echo Closed-bar evaluator active; 4-bar retest window; 2R target.
echo Safety: QQQ/SPY proxy feeds are monitoring-only and cannot fire live alerts.
echo True futures feed is required for actionable NYSE-open signals.
echo Preflight endpoint: http://127.0.0.1:%TMBT_NEXT_PORT%/api/preflight
echo.
start "" "http://127.0.0.1:%TMBT_NEXT_PORT%"
py -3 server_boot.py
if errorlevel 1 python server_boot.py
pause
