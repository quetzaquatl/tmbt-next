@echo off
setlocal
cd /d "%~dp0"
if not exist next_ui.pid (
  echo TMBT Next PID file not found.
  pause
  exit /b 0
)
set /p PID=<next_ui.pid
echo Stopping TMBT Next PID %PID% ...
taskkill /PID %PID% /T /F >nul 2>&1
del /q next_ui.pid >nul 2>&1
echo Done.
