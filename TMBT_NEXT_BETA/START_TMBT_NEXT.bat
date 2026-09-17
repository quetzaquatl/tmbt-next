@echo off
setlocal
title TMBT Next Beta
cd /d "%~dp0"
if not defined TMBT_WORKSPACE set "TMBT_WORKSPACE=D:\Projekt model\Trading_Model_Backtest_Studio_WORKSPACE"
set "TMBT_NEXT_PORT=8510"
echo.
echo ======================================
echo TMBT NEXT BETA 0.9.4 ORIGINAL PIPELINE
echo ======================================
echo Existing Streamlit Studio stays unchanged.
echo Workspace: %TMBT_WORKSPACE%
echo URL: http://127.0.0.1:%TMBT_NEXT_PORT%
echo Data: original TMBT 4.6 Twelve live mirror with local SQLite fallback.
echo Feed diagnostics: /api/feed-status and /api/diagnostics.
echo Yahoo/GC proxy fallback: OFF.
echo.
start "" "http://127.0.0.1:%TMBT_NEXT_PORT%"
py -3 server_original.py
if errorlevel 1 python server_original.py
pause
