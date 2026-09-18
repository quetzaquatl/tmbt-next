@echo off
setlocal
title TMBT Studio Migration Verification
cd /d "%~dp0"
if not defined TMBT_WORKSPACE set "TMBT_WORKSPACE=D:\Projekt model\Trading_Model_Backtest_Studio_WORKSPACE"
py -3 migration_verify.py
if errorlevel 1 python migration_verify.py
echo.
echo Report:
echo %TMBT_WORKSPACE%\migration\migration_verification.json
pause
