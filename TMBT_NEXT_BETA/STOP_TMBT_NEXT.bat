@echo off
setlocal
cd /d "%~dp0"
set "PORT=8510"

echo Stopping TMBT Next ...

rem First stop the PID recorded by the current build, if present.
if exist next_ui.pid (
  set /p PID=<next_ui.pid
  if defined PID (
    echo Stopping recorded PID %PID% ...
    taskkill /PID %PID% /T /F >nul 2>&1
  )
  del /q next_ui.pid >nul 2>&1
)

rem Older builds could leave a Python HTTP server alive without a valid PID file.
rem Port 8510 is dedicated to TMBT Next, so clean any stale listener as well.
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /R /C:":%PORT% .*LISTENING"') do (
  echo Stopping stale listener on port %PORT% PID %%P ...
  taskkill /PID %%P /T /F >nul 2>&1
)

timeout /t 1 /nobreak >nul

echo Done.
