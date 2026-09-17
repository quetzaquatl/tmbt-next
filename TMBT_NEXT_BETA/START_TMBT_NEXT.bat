@echo off
setlocal
title TMBT Next Beta
cd /d "%~dp0"
if not defined TMBT_WORKSPACE set "TMBT_WORKSPACE=D:\Projekt model\Trading_Model_Backtest_Studio_WORKSPACE"
set "TMBT_NEXT_PORT=8510"
echo.
echo =========================================
echo TMBT NEXT BETA 0.9.11 CANONICAL STRICT
echo =========================================
echo Existing Streamlit Studio stays unchanged.
echo Workspace: %TMBT_WORKSPACE%
echo URL: http://127.0.0.1:%TMBT_NEXT_PORT%
echo Feed owner: Old Studio Twelve collector only.
echo TMBT Next never starts or stops Twelve itself.
echo Canonical model/chart feeds:
echo   NQ  = TWELVE:QQQ
echo   ES  = TWELVE:SPY
echo   XAU = TWELVE:XAU/USD
echo 30m is derived locally from canonical 15m bars.
echo Cross-scale local futures/Yahoo fallback: DISABLED.
echo.
start "" "http://127.0.0.1:%TMBT_NEXT_PORT%"
py -3 server_boot.py
if errorlevel 1 python server_boot.py
pause
