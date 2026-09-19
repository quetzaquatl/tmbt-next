@echo off
setlocal
cd /d "%~dp0"
echo.
echo =========================================
echo TMBT NEXT - VERIFY ICT CORE AUDIT
echo =========================================
py -3 verify_ict_core_patch.py
if errorlevel 1 python verify_ict_core_patch.py
if errorlevel 1 (
  echo.
  echo VERIFY FAILED
  pause
  exit /b 1
)
echo.
echo VERIFY PASSED
pause
