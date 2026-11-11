@echo off
cd /d "%~dp0"

REM Usage: run.bat YOUR_PASSWORD
REM Password stays in the process environment only, never written to a file.
if not "%~1"=="" set "CMATC_PWD=%~1"

if not defined CMATC_PWD (
  echo.
  echo   Please set the password first, either:
  echo     1^) in this window:  set "CMATC_PWD=YOUR_PASSWORD"   then run run.bat
  echo     2^) directly:        run.bat YOUR_PASSWORD
  echo.
  echo   NOTE: do NOT use   set CMATC_PWD='password'
  echo         The single quotes become part of the password and login fails.
  echo.
  pause
  exit /b 1
)

set "PY=D:\Base\usr\miniconda3\python.exe"
if not exist "%PY%" set "PY=python"

echo Starting auto study ^(serial; exits automatically at 80 credit hours^).
echo To stop: create an empty file named stop.flag in this folder, or close this window.
echo.
"%PY%" -u auto_study.py
echo.
pause
