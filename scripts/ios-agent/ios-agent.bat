@echo off
rem TestHub iOS Agent launcher (double-click friendly)
rem   ios-agent.bat            -> -Mode watch  (resident; keep the window open)
rem   ios-agent.bat watch      -> -Mode watch  (resident)
rem   ios-agent.bat start      -> -Mode start  (one-shot)
rem   ios-agent.bat stop       -> -Mode stop
rem   ios-agent.bat dryrun     -> -Mode start -DryRun
setlocal
cd /d "%~dp0"

rem share_on_lan=true（同事机器）需要管理员：自动请求提权
set "NEED_ADMIN=0"
if exist "agent.config.json" (
  findstr /i /r /c:"share_on_lan.*true" agent.config.json >nul 2>&1 && set "NEED_ADMIN=1"
)
if "%NEED_ADMIN%"=="1" (
  net session >nul 2>&1
  if errorlevel 1 (
    echo Requesting administrator privileges...
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -ArgumentList '%*' -Verb RunAs"
    exit /b
  )
)

set "MODE=%~1"
set "PAUSEIT=0"
if "%MODE%"=="" (
  set "MODE=watch"
  set "PAUSEIT=1"
)

if /I "%MODE%"=="dryrun" (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0ios-agent.ps1" -Mode start -DryRun
) else (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0ios-agent.ps1" -Mode %MODE%
)

set "RC=%ERRORLEVEL%"
echo.
echo [ios-agent exit=%RC%]
if "%PAUSEIT%"=="1" pause
endlocal
