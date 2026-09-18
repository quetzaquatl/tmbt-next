@echo off
setlocal
title TMBT Auto Research Status
cd /d "%~dp0"
if not defined TMBT_WORKSPACE set "TMBT_WORKSPACE=D:\Projekt model\Trading_Model_Backtest_Studio_WORKSPACE"
py -3 research_scheduler.py --status
if errorlevel 1 python research_scheduler.py --status
echo.
echo Latest report:
echo %TMBT_WORKSPACE%\research_reports\latest.md
pause
