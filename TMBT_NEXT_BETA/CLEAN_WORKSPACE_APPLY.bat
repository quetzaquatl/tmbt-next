@echo off
setlocal
title TMBT Workspace Cleanup - APPLY SAFE ARCHIVE
cd /d "%~dp0"
if not defined TMBT_WORKSPACE set "TMBT_WORKSPACE=D:\Projekt model\Trading_Model_Backtest_Studio_WORKSPACE"
echo.
echo This copies/verifies legacy live mirrors into live_data and moves the old roots
echo to _legacy_archive. It does NOT permanently delete them.
echo.
py -3 workspace_cleanup.py --workspace "%TMBT_WORKSPACE%" --apply
if errorlevel 1 python workspace_cleanup.py --workspace "%TMBT_WORKSPACE%" --apply
echo.
echo Report:
echo %TMBT_WORKSPACE%\migration\workspace_cleanup_apply.json
pause
