@echo off
REM Pokemon Buddy for Claude - Windows installer
REM Double-click or run: install.bat

where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
  echo.
  echo   Error: Python is not installed or not on PATH.
  echo   Install it from https://www.python.org/downloads/
  echo   Be sure to check "Add Python to PATH" during install.
  echo.
  pause
  exit /b 1
)

python "%~dp0install.py"
pause
