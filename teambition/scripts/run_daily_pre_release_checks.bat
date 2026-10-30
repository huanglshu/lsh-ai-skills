@echo off
setlocal

cd /d %~dp0
python run_daily_pre_release_checks.py
set EXIT_CODE=%ERRORLEVEL%

if not "%EXIT_CODE%"=="0" (
  echo.
  echo [FAIL] 发布前检查未通过，请先修复后再发布。
  exit /b %EXIT_CODE%
)

echo.
echo [PASS] 发布前检查通过。
exit /b 0
