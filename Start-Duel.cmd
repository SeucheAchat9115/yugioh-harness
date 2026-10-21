@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo First run: follow the Windows setup in docs\player-ui.md.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m harness.cli play --repo "%CD%"
if errorlevel 1 pause
