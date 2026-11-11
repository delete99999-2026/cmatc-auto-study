@echo off
chcp 65001 >nul 2>&1
setlocal
cd /d "%~dp0"

rem ============================================================
rem  One-shot cleanup of corrupted resume position (videoTime=3600)
rem  v2: scans ALL courses, not just the first one.
rem  Usage:  run_reset.bat YourPassword  [dry]
rem  NOTE: do NOT use   set CMATC_PWD='password'
rem        correct is   set "CMATC_PWD=password"
rem ============================================================

if not "%~1"=="" set "CMATC_PWD=%~1"
if /i "%~2"=="dry" set "CMATC_DRY_RUN=1"

set "PY=D:\Base\usr\miniconda3\python.exe"

echo.
echo  Reset videoTime (resume position) back to 0 - v2 full scan.
echo  Scans ALL courses for videoTime ^>= 3500 and zeroes only those.
echo  This ONLY restores the starting position of the video.
echo  It does NOT add study time, does NOT mark anything completed.
echo  2nd arg: "dry" = query only. "diag" belongs to run_steady.bat, not here.
echo  Result file: reset_video_time_out.txt
echo.

if not defined CMATC_PWD (
  echo  ERROR: password missing.
  echo  Usage: run_reset.bat YourPassword
  echo         run_reset.bat YourPassword dry   ^(query only, no write^)
  goto :eof
)

if defined CMATC_DRY_RUN (
  echo  *** DRY MODE: query only, no write. ***
)

"%PY%" -u reset_video_time.py

echo.
echo  Finished. Press any key to close...
pause >nul
endlocal
