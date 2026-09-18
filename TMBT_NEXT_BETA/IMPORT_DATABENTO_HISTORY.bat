@echo off
setlocal
title TMBT Databento Historical Import
cd /d "%~dp0"
if not defined TMBT_WORKSPACE set "TMBT_WORKSPACE=D:\Projekt model\Trading_Model_Backtest_Studio_WORKSPACE"

echo.
echo =========================================
echo TMBT DATABENTO HISTORICAL IMPORT
echo =========================================
echo Raw folder:
echo %TMBT_WORKSPACE%\historical\databento\raw
echo.
echo NQ / ES / GC OHLCV-1m -^> local SQLite
echo 1m / 5m / 15m / 30m / 1H
echo Raw DBN files remain untouched.
echo.

py -3 -c "import databento, pandas" >nul 2>&1
if errorlevel 1 (
  echo Installing Python packages databento + pandas ...
  py -3 -m pip install --user databento pandas
  if errorlevel 1 goto :fallback_install
)

py -3 databento_history_import.py --workspace "%TMBT_WORKSPACE%"
if errorlevel 1 goto :failed
goto :done

:fallback_install
python -m pip install --user databento pandas
if errorlevel 1 goto :failed
python databento_history_import.py --workspace "%TMBT_WORKSPACE%"
if errorlevel 1 goto :failed

:done
echo.
echo Import complete.
echo Database:
echo %TMBT_WORKSPACE%\historical\databento\tmbt_futures_history.sqlite
echo Status:
echo %TMBT_WORKSPACE%\historical\databento\import_status.json
pause
exit /b 0

:failed
echo.
echo Import failed. Check:
echo %TMBT_WORKSPACE%\historical\databento\import_status.json
pause
exit /b 1
