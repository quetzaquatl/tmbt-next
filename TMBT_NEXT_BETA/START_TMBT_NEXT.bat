@echo off
setlocal
title TMBT Next Beta
cd /d "%~dp0"
if not defined TMBT_WORKSPACE set "TMBT_WORKSPACE=D:\Projekt model\Trading_Model_Backtest_Studio_WORKSPACE"
if not defined TMBT_TWELVE_DIR set "TMBT_TWELVE_DIR=D:\Projekt model\Trading_Model_Backtest_Studio_v3_7_DEV"
set "TMBT_NEXT_PORT=8510"
echo.
echo ======================================
echo TMBT NEXT BETA 0.9.9 LEGACY FEED BRIDGE
echo ======================================
echo Existing Streamlit Studio stays unchanged.
echo Workspace: %TMBT_WORKSPACE%
echo Legacy Twelve app: %TMBT_TWELVE_DIR%
echo URL: http://127.0.0.1:%TMBT_NEXT_PORT%
echo Credential bridge: reuse the old studio Twelve config without printing the key.
echo Collector starts only when a valid legacy key is found.
echo Feed safety: NQ / ES / XAU stay isolated by market and timeframe.
echo XAU: original TWELVE:XAU/USD. Yahoo/GC proxy OFF.
echo 30m: derived from original 15m bars.
echo.
start "" "http://127.0.0.1:%TMBT_NEXT_PORT%"
py -3 server_boot.py
if errorlevel 1 python server_boot.py
pause
