@echo off
echo Stopping current server processes...

REM Kill any existing processes on ports 8000 and 8001
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000') do (
    echo Killing process %%a on port 8000
    taskkill /PID %%a /F >nul 2>&1
)

for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8001') do (
    echo Killing process %%a on port 8001
    taskkill /PID %%a /F >nul 2>&1
)

echo Waiting 3 seconds for processes to fully terminate...
timeout /t 3 /nobreak >nul

echo Starting Link Profiler API server...
cd /d "C:\Users\hp\Documents\Projects\Domain_Research\Link_Profiler_Repo\Link_Profiler"

REM Start the main API server
echo Starting main API on port 8000...
start "Link Profiler API" cmd /k "python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload"

echo.
echo ====================================
echo Link Profiler Server Started!
echo ====================================
echo.
echo Customer Dashboard: https://customer.yspanel.com
echo Mission Control:    https://monitor.yspanel.com
echo API Docs:          http://localhost:8000/docs
echo.
echo Press any key to exit this script (servers will continue running)
pause >nul
