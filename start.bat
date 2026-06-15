@echo off
cd /d E:\TestHub\testhub_platform

echo ========================================
echo   TestHub Startup Script
echo ========================================
echo.

echo [1/5] Killing old processes on ports 3000 and 8000...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr /R ":3000 .*LISTENING"') do taskkill /F /PID %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano ^| findstr /R ":8000 .*LISTENING"') do taskkill /F /PID %%a >nul 2>&1
echo   Done.

echo.
echo [2/5] Starting MySQL...
start "" /B "C:\Program Files\MySQL\MySQL Server 8.0\bin\mysqld.exe" --datadir="E:\TestHub\mysql_data" --port=3307
timeout /t 2 /nobreak >nul
echo   MySQL started on port 3307

echo.
echo [3/5] Starting Redis...
start "" /B "C:\Program Files\Redis\redis-server.exe"
timeout /t 1 /nobreak >nul
echo   Redis started

echo.
echo [4/5] Starting Django backend...
start "Django" cmd /c "cd /d E:\TestHub\testhub_platform && call venv\Scripts\activate.bat && python manage.py runserver 0.0.0.0:8000"
timeout /t 4 /nobreak >nul

echo.
echo [5/5] Starting Vite frontend...
start "Vite" cmd /c "cd /d E:\TestHub\testhub_platform\frontend && npm run dev"

echo.
echo ========================================
echo   All services started!
echo   Frontend : http://localhost:3000
echo   Backend  : http://localhost:8000
echo   Admin    : http://localhost:8000/admin/
echo ========================================
echo.
pause
