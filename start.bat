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

echo [1/5] Checking existing services...
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
echo [2/5] Starting MySQL...
start "" /B "C:\Program Files\MySQL\MySQL Server 8.0\bin\mysqld.exe" --datadir="E:\TestHub\mysql_data" --port=3307 --skip-log-bin
timeout /t 2 /nobreak >nul
echo   MySQL started on port 3307

echo.
echo [3/5] Starting Redis...
start "" /B "C:\Program Files\Redis\redis-server.exe"
timeout /t 1 /nobreak >nul
echo   Redis started

echo.
echo [4/6] Starting Django backend...
if "%DJANGO_RUNNING%"=="1" (
    echo   Django already listening on 8000 - skipped.
) else (
    start "Django" cmd /c "cd /d E:\TestHub\testhub_platform && call venv\Scripts\activate.bat && python manage.py runserver 0.0.0.0:8000"
    timeout /t 4 /nobreak >nul
    echo   Django started on port 8000
)

echo.
echo [5/6] Starting Celery worker...
start "Celery" cmd /c "cd /d E:\TestHub\testhub_platform && call venv\Scripts\activate.bat && celery -A backend worker --loglevel=info --pool=solo"
timeout /t 3 /nobreak >nul
echo   Celery worker started

echo.
echo [6/6] Starting Vite frontend...
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
