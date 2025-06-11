@echo off
echo ====================================
echo Link Profiler Server Restart Script
echo ====================================

echo.
echo Stopping any existing server processes...
taskkill /F /IM python.exe /T 2>nul || echo No Python processes found

echo.
echo Waiting 3 seconds for processes to fully terminate...
timeout /t 3 /nobreak >nul

echo.
echo Starting Link Profiler server...
cd /d "C:\Users\hp\Documents\Projects\Domain_Research\Link_Profiler_Repo\Link_Profiler"

echo.
echo Loading environment variables...
call export_env.sh 2>nul || echo Environment script not found, using .env file

echo.
echo Starting server with uvicorn...
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

echo.
echo Server stopped.
pause
