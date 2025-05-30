@echo off
REM Windows version of local startup script

echo Starting Link Profiler Queue System (Local Development)

REM Check if Redis is running (requires Redis CLI in PATH)
redis-cli ping >nul 2>&1
if %errorlevel% neq 0 (
    echo Redis is not running. Please start Redis first:
    echo   Docker: docker run -d -p 6379:6379 redis:7-alpine
    echo   Or install Redis for Windows
    exit /b 1
)

echo Redis is running

REM Check if virtual environment exists
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Install dependencies
echo Installing dependencies...
pip install -r requirements.txt

REM Start components
echo Starting coordinator...
start "Coordinator" python -m queue_system.job_coordinator

echo Starting satellite crawler...
start "Satellite" python -m queue_system.satellite_crawler --region local-dev

echo Starting monitoring dashboard...
start "Monitor" python -m monitoring.dashboard dashboard

echo All components started!
echo API: http://localhost:8000
echo Monitor: http://localhost:8001
echo API Docs: http://localhost:8000/docs

pause