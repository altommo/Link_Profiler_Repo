#!/bin/bash

echo "======================================"
echo "Link Profiler Server Restart Script"
echo "======================================"

echo
echo "Stopping any existing server processes..."
pkill -f "uvicorn main:app" || echo "No uvicorn processes found"
pkill -f "python.*main.py" || echo "No main.py processes found"

echo
echo "Waiting 3 seconds for processes to fully terminate..."
sleep 3

echo
echo "Starting Link Profiler server..."
cd "$(dirname "$0")"

echo
echo "Loading environment variables..."
if [ -f ".env" ]; then
    export $(cat .env | grep -v '^#' | xargs)
    echo "Environment variables loaded from .env"
else
    echo "Warning: .env file not found"
fi

echo
echo "Starting server with uvicorn..."
nohup uvicorn main:app --host 0.0.0.0 --port 8000 --reload > server.log 2>&1 &

echo "Server started in background. PID: $!"
echo "To view logs: tail -f server.log"
echo "To stop server: pkill -f 'uvicorn main:app'"
