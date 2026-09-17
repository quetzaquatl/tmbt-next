@echo off
setlocal
title TMBT Massive Futures Bridge
cd /d "%~dp0"
if not defined TMBT_WORKSPACE set "TMBT_WORKSPACE=D:\Projekt model\Trading_Model_Backtest_Studio_WORKSPACE"
echo.
echo =========================================
echo TMBT MASSIVE FUTURES BRIDGE
echo =========================================
echo Workspace: %TMBT_WORKSPACE%
echo Default contracts for 2026-09-17 roll: NQZ6 / ESZ6
echo Override with TMBT_NQ_CONTRACT / TMBT_ES_CONTRACT if required.
echo.
if not defined MASSIVE_API_KEY (
  echo ERROR: MASSIVE_API_KEY is not set.
  echo Store it as a Windows User environment variable, then open a new terminal.
  pause
  exit /b 2
)
py -3 -c "import massive" >nul 2>nul
if errorlevel 1 (
  echo Python package massive-api-client is missing.
  echo Install once with: py -3 -m pip install -U massive-api-client
  pause
  exit /b 3
)
py -3 massive_futures_bridge.py
if errorlevel 1 python massive_futures_bridge.py
pause
