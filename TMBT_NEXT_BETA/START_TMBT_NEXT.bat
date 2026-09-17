@echo off
setlocal
title TMBT Next Beta
cd /d "%~dp0"
if not defined TMBT_WORKSPACE set "TMBT_WORKSPACE=D:\Projekt model\Trading_Model_Backtest_Studio_WORKSPACE"
set "TMBT_NEXT_PORT=8510"
echo.
echo ======================================
echo TMBT NEXT BETA 0.9.2 LIVE CHARTS
echo ======================================
echo Existing Streamlit Studio stays unchanged.
echo Workspace: %TMBT_WORKSPACE%
echo URL: http://127.0.0.1:%TMBT_NEXT_PORT%
echo NQ/ES/XAU chart feed: temporary fresh fallback; local cache remains fallback.
echo.
start "" "http://127.0.0.1:%TMBT_NEXT_PORT%"
py -3 server_live_all.py
if errorlevel 1 python server_live_all.py
pause
