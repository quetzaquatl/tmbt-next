@echo off
setlocal
title TMBT Next Beta
cd /d "%~dp0"
if not defined TMBT_WORKSPACE set "TMBT_WORKSPACE=D:\Projekt model\Trading_Model_Backtest_Studio_WORKSPACE"
if not defined TMBT_TWELVE_DIR set "TMBT_TWELVE_DIR=D:\Projekt model\Trading_Model_Backtest_Studio_v3_7_DEV"
set "TMBT_NEXT_PORT=8510"
echo.
echo ======================================
echo TMBT NEXT BETA 0.9.7 LIVE DESK
echo ======================================
echo Existing Streamlit Studio stays unchanged.
echo Workspace: %TMBT_WORKSPACE%
echo Twelve collector: %TMBT_TWELVE_DIR%
echo URL: http://127.0.0.1:%TMBT_NEXT_PORT%
echo Data: original Twelve collector -> shared live_data -> models + TMBT Next.
echo XAU: TWELVE:XAU/USD from the original collector. No Yahoo/GC proxy.
echo 30m: derived from original 15m bars.
echo.
start "" "http://127.0.0.1:%TMBT_NEXT_PORT%"
py -3 server_boot.py
if errorlevel 1 python server_boot.py
pause
