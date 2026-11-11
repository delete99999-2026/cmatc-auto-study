@echo off
cd /d "%~dp0"

REM Usage: run_fast.bat YOUR_PASSWORD
REM Password stays in the process environment only, never written to a file.
if not "%~1"=="" set "CMATC_PWD=%~1"

if not defined CMATC_PWD (
  echo.
  echo   Please set the password first:
  echo     set "CMATC_PWD=YOUR_PASSWORD"   then run run_fast.bat
  echo   or:  run_fast.bat YOUR_PASSWORD
  echo.
  echo   NOTE: do NOT use   set CMATC_PWD='password'
  echo         single quotes become part of the password and login fails.
  echo.
  echo   IMPORTANT: stop auto_study.py FIRST
  echo         ^(this platform uses single-login; starting this script
  echo          will kick out the other running session^).
  echo.
  pause
  exit /b 1
)

set "PY=D:\Base\usr\miniconda3\python.exe"
if not exist "%PY%" set "PY=python"

echo Starting FAST study ^(single-window rotation; auto-exits at 80 credit hours^).
echo To stop: create an empty file named stop_fast.flag in this folder.
echo.
"%PY%" -u fast_study.py
echo.
pause
