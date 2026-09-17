@echo off
setlocal
title TMBT Next Beta
cd /d "%~dp0"
if not defined TMBT_WORKSPACE set "TMBT_WORKSPACE=D:\Projekt model\Trading_Model_Backtest_Studio_WORKSPACE"
set "TMBT_NEXT_PORT=8510"
echo.
echo ======================================
echo TMBT NEXT BETA 0.9.8 STABLE FEED
echo ======================================
echo Existing Streamlit Studio stays unchanged.
echo Workspace: %TMBT_WORKSPACE%
echo URL: http://127.0.0.1:%TMBT_NEXT_PORT%
echo Feed safety: NQ / ES / XAU are isolated by market and timeframe.
echo Market-data collectors are NOT auto-started by the UI.
echo XAU direct recovery only activates when a valid Twelve API key exists.
echo 30m: derived from original 15m bars.
echo Yahoo/GC proxy fallback: OFF.
echo.
start "" "http://127.0.0.1:%TMBT_NEXT_PORT%"
py -3 server_boot.py
if errorlevel 1 python server_boot.py
pause
