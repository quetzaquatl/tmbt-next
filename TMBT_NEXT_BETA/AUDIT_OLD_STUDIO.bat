@echo off
setlocal
title TMBT Old Studio Migration Audit
cd /d "%~dp0"
if not defined TMBT_WORKSPACE set "TMBT_WORKSPACE=D:\Projekt model\Trading_Model_Backtest_Studio_WORKSPACE"
if not defined TMBT_OLD_STUDIO_ROOT set "TMBT_OLD_STUDIO_ROOT=D:\Projekt model\Trading_Model_Backtest_Studio_v3_7_DEV"

echo Auditing old Studio and building source bundle...
py -3 old_studio_migration_audit.py --old-root "%TMBT_OLD_STUDIO_ROOT%" --workspace "%TMBT_WORKSPACE%" --bundle
if errorlevel 1 python old_studio_migration_audit.py --old-root "%TMBT_OLD_STUDIO_ROOT%" --workspace "%TMBT_WORKSPACE%" --bundle
echo.
echo Output:
echo %TMBT_WORKSPACE%\migration\old_studio_audit.json
echo %TMBT_WORKSPACE%\migration\old_studio_source_bundle.zip
pause
