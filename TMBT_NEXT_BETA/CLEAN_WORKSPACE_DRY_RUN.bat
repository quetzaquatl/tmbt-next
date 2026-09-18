@echo off
setlocal
title TMBT Workspace Cleanup - DRY RUN
cd /d "%~dp0"
if not defined TMBT_WORKSPACE set "TMBT_WORKSPACE=D:\Projekt model\Trading_Model_Backtest_Studio_WORKSPACE"
py -3 workspace_cleanup.py --workspace "%TMBT_WORKSPACE%"
if errorlevel 1 python workspace_cleanup.py --workspace "%TMBT_WORKSPACE%"
echo.
echo DRY RUN only. No files were moved.
echo Review:
echo %TMBT_WORKSPACE%\migration\workspace_cleanup_dry_run.json
pause
