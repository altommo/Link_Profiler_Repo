#!/bin/bash
# Local Development Startup Script

echo "🚀 Starting Link Profiler Queue System (Local Development)"

# Check if Redis is running
if ! redis-cli ping > /dev/null 2>&1; then
    echo "❌ Redis is not running. Please start Redis first:"
    echo "   Ubuntu/Debian: sudo systemctl start redis"
    echo "   macOS: brew services start redis" 
    echo "   Docker: docker run -d -p 6379:6379 redis:7-alpine"
    exit 1
fi

echo "✅ Redis is running"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies
echo "📦 Installing dependencies..."
pip install -r requirements.txt

# Start components in background
echo "🚀 Starting coordinator..."
python -m queue_system.job_coordinator &
COORDINATOR_PID=$!

echo "🛰️ Starting satellite crawler..."
python -m queue_system.satellite_crawler --region local-dev &
SATELLITE_PID=$!

echo "📊 Starting monitoring dashboard..."
python -m monitoring.dashboard dashboard &
MONITOR_PID=$!

echo "✅ All components started!"
echo "🌐 API: http://localhost:8000"
echo "📊 Monitor: http://localhost:8001"
echo "📖 API Docs: http://localhost:8000/docs"

# Wait for interrupt
trap "kill $COORDINATOR_PID $SATELLITE_PID $MONITOR_PID" EXIT
wait