@echo off
chcp 65001 >nul 2>&1
setlocal

rem ============================================================
rem  FAST study v2 launcher (pure ASCII to avoid CMD codepage issues)
rem  Usage:  run_fast_v2.bat YourPassword  [diag]
rem  NOTE: do NOT use   set CMATC_PWD='password'
rem        correct is   set "CMATC_PWD=password"
rem ============================================================

if not "%~1"=="" set "CMATC_PWD=%~1"
if /i "%~2"=="diag" set "CMATC_DIAG=1"

set "PY=D:\Base\usr\miniconda3\python.exe"

echo.
echo  Starting FAST study v2 (real _learnspace popup + HTTP course selection + strict SCORM API check).
echo  Auto-exits at 80 credit hours.
echo  IMPORTANT: SSO kicks other sessions. Stop auto_study.py / fast_study.py FIRST.
echo  To stop gracefully: create an empty file named  stop_fast_v2.flag  in this folder.
echo  Logs: fast_v2_run.log  /  fast_v2_requests.log
echo.

if not defined CMATC_PWD (
  echo  ERROR: password missing.
  echo  Usage: run_fast_v2.bat YourPassword
  echo     or: set "CMATC_PWD=YourPassword"  then  python -u fast_study_v2.py
  goto :eof
)

if defined CMATC_DIAG (
  echo  *** DIAG MODE: only one course, prints API/frame/request details, then exits. ***
)

"%PY%" -u fast_study_v2.py

echo.
echo  Finished. Press any key to close...
pause >nul
endlocal
