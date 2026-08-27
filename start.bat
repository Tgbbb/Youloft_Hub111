@echo off
cd /d E:\TestHub\testhub_platform

echo ========================================
echo   TestHub Startup Script
echo ========================================
echo.

rem Usage: start.bat          -> start missing services, keep running ones
rem        start.bat restart  -> kill and restart everything on ports 3000/8000
set RESTART_ALL=0
if /I "%~1"=="restart" set RESTART_ALL=1

echo [1/7] Checking existing services...
set VITE_RUNNING=0
set DJANGO_RUNNING=0
netstat -ano | findstr /R ":3000[^0-9].*LISTENING" >nul 2>&1 && set VITE_RUNNING=1
netstat -ano | findstr /R ":8000[^0-9].*LISTENING" >nul 2>&1 && set DJANGO_RUNNING=1

if "%RESTART_ALL%"=="1" (
    echo   Restart mode: killing old processes on ports 3000 and 8000...
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr /R ":3000[^0-9].*LISTENING"') do taskkill /F /PID %%a >nul 2>&1
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr /R ":8000[^0-9].*LISTENING"') do taskkill /F /PID %%a >nul 2>&1
    set VITE_RUNNING=0
    set DJANGO_RUNNING=0
    echo   Done.
) else (
    echo   Vite port 3000: %VITE_RUNNING% (1=running, 0=free)
    echo   Django port 8000: %DJANGO_RUNNING% (1=running, 0=free)
)

echo.
echo [2/7] Starting MySQL...
set MYSQL_RUNNING=0
netstat -ano | findstr /R ":3307[^0-9].*LISTENING" >nul 2>&1 && set MYSQL_RUNNING=1
if "%MYSQL_RUNNING%"=="1" (
    echo   MySQL already listening on 3307 - skipped.
    goto mysql_done
)
rem -- no live MySQL on 3307; check another MySQL service (3306) is not running before force-kill
netstat -ano | findstr /R ":3306[^0-9].*LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo   WARNING: another MySQL appears on 3306 - not force-killing mysqld, starting anyway.
    goto mysql_start
)
echo   Cleaning any stale mysqld (testhub datadir)...
taskkill /F /IM mysqld.exe >nul 2>&1
ping -n 3 127.0.0.1 >nul
:mysql_start
start "MySQL" "C:\Program Files\MySQL\MySQL Server 8.0\bin\mysqld.exe" --datadir="E:\TestHub\mysql_data" --port=3307 --skip-log-bin --console
echo   Waiting up to 20s for MySQL to accept connections...
for /l %%i in (1,1,10) do (
    ping -n 2 127.0.0.1 >nul
    netstat -ano | findstr /R ":3307[^0-9].*LISTENING" >nul 2>&1 && goto mysql_up
)
echo   WARNING: 3307 not listening after 20s - check E:\TestHub\mysql_data\PC-20180703SHEM.err
goto mysql_done
:mysql_up
echo   MySQL started on port 3307
:mysql_done

echo.
echo [3/7] Starting Redis...
start "" /B "C:\Program Files\Redis\redis-server.exe"
timeout /t 1 /nobreak >nul
echo   Redis started

echo.
echo [4/7] Starting Django backend...
if "%DJANGO_RUNNING%"=="1" (
    echo   Django already listening on 8000 - skipped.
) else (
    start "Django" cmd /c "cd /d E:\TestHub\testhub_platform && call venv\Scripts\activate.bat && python manage.py runserver 0.0.0.0:8000"
    timeout /t 4 /nobreak >nul
    echo   Django started on port 8000
)

echo.
echo [5/7] Starting Celery worker...
start "Celery" cmd /c "cd /d E:\TestHub\testhub_platform && call venv\Scripts\activate.bat && celery -A backend worker --loglevel=info --pool=threads --concurrency=4"
timeout /t 3 /nobreak >nul
echo   Celery worker started

echo.
echo [6/7] Starting Celery beat...
start "CeleryBeat" cmd /c "cd /d E:\TestHub\testhub_platform && call venv\Scripts\activate.bat && celery -A backend beat --loglevel=info"
timeout /t 2 /nobreak >nul
echo   Celery beat started

echo.
echo [7/7] Starting Vite frontend...
if "%VITE_RUNNING%"=="1" (
    echo   Vite already listening on 3000 - skipped.
) else (
    start "Vite" cmd /c "cd /d E:\TestHub\testhub_platform\frontend && npm run dev > vite-dev.log 2>&1"
    echo   Vite started - logs saved to frontend\vite-dev.log
)

echo.
echo ========================================
echo   All services started!
echo   Frontend : http://localhost:3000
echo   Backend  : http://localhost:8000
echo   Admin    : http://localhost:8000/admin/
echo ========================================
echo.
pause
