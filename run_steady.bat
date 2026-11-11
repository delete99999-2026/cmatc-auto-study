@echo off
chcp 65001 >nul 2>&1
setlocal
cd /d "%~dp0"

rem ============================================================
rem  STEADY study launcher (pure ASCII to avoid CMD codepage issues)
rem
rem  Usage:
rem    run_steady.bat <user> <password> [target] [diag|dry]
rem    run_steady.bat <password> [diag|dry]            (legacy form)
rem  Examples:
rem    run_steady.bat YOUR_ACCOUNT YOUR_PASSWORD          -> target 80 (default)
rem    run_steady.bat YOUR_ACCOUNT YOUR_PASSWORD 100
rem    run_steady.bat YOUR_ACCOUNT YOUR_PASSWORD 100 dry
rem  (account is required; no real account is stored in this repository)
rem
rem  Do NOT write   set CMATC_PWD='password'
rem  Correct is     set "CMATC_PWD=password"
rem ============================================================

set "PY=D:\Base\usr\miniconda3\python.exe"
set "U="
set "P="
set "T="
set "M="

if "%~1"=="" goto :nopwd
rem ---- legacy detection: 2nd arg is a mode (or missing) => 1st is password
if /i "%~2"=="diag" goto :legacy
if /i "%~2"=="dry"  goto :legacy
if "%~2"==""        goto :legacy

set "U=%~1"
set "P=%~2"
set "T=%~3"
if /i "%~3"=="diag" (set "T=" & set "M=diag")
if /i "%~3"=="dry"  (set "T=" & set "M=dry")
if /i "%~4"=="diag" set "M=diag"
if /i "%~4"=="dry"  set "M=dry"
goto :run

:legacy
set "P=%~1"
if /i "%~2"=="diag" set "M=diag"
if /i "%~2"=="dry"  set "M=dry"
goto :run

:nopwd
set "P="

:run
if not defined P (
  echo  ERROR: password missing.
  echo  Usage: run_steady.bat ^<user^> ^<password^> [target] [diag^|dry]
  echo         default target = 80 credit hours
  goto :eof
)

set "MFLAG="
if /i "%M%"=="diag" set "MFLAG=--diag"
if /i "%M%"=="dry"  set "MFLAG=--dry"

echo.
echo  Starting STEADY study: real online time, real playback, NO timing forgery.
echo  ARGS: user=password=target as startup params; default target = 80 credit hours.
if defined T (echo  Target credit hours: %T%) else (echo  Target credit hours: 80 ^(default^))
echo  AUTO-CHOOSE: when all selected courses are 100%% but target hours not met,
echo    pick NEW courses from Course Center; NEVER re-select a studied course.
echo    Exclusion by courseId / openId / full title / persistent history file.
echo  RULE: finish ONE course to 100%% before moving to the next one.
echo  RESUME: jump to first UNFINISHED node; UNFINISHED node plays from 0s.
echo  QUIZZES: auto-answers self-tests via the platform's own submit button.
echo  POOL: study list from the "unfinished" tab of My Courses, deduped by courseId.
echo  MODE: diag = one-course diagnostic; dry = read-only report (no writes).
echo  Strictly ONE learnspace window at a time (serial). SSO kicks other sessions.
echo  To stop gracefully: create an empty file named  stop_steady.flag  in this folder.
echo  Logs: steady_run.log  /  steady_requests.log
echo.
if defined MFLAG echo  *** MODE: %M% ***
echo.

"%PY%" -u steady_study_fixed.py --user "%U%" --pwd "%P%" --target "%T%" %MFLAG%

echo.
echo  Finished. Press any key to close...
pause >nul
endlocal
