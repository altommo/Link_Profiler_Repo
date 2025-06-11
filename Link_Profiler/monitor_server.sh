#!/bin/bash

echo "======================================"
echo "Link Profiler Server Log Monitor"
echo "======================================"

# Function to show server status
show_status() {
    echo
    echo "=== Server Status ==="
    if pgrep -f "uvicorn main:app" > /dev/null; then
        echo "✅ Server is running"
        echo "PID: $(pgrep -f 'uvicorn main:app')"
    else
        echo "❌ Server is not running"
    fi
}

# Function to show recent WebSocket logs
show_websocket_logs() {
    echo
    echo "=== Recent WebSocket Logs ==="
    if [ -f "server.log" ]; then
        grep -i "websocket\|mission-control\|ws/" server.log | tail -20
    else
        echo "No server.log file found"
    fi
}

# Function to show recent errors
show_errors() {
    echo
    echo "=== Recent Errors ==="
    if [ -f "server.log" ]; then
        grep -i "error\|exception\|failed" server.log | tail -10
    else
        echo "No server.log file found"
    fi
}

# Function to monitor logs in real-time
monitor_logs() {
    echo
    echo "=== Live Log Monitoring (Press Ctrl+C to stop) ==="
    if [ -f "server.log" ]; then
        tail -f server.log | grep --line-buffered -E "(websocket|mission-control|ws/|error|exception)"
    else
        echo "No server.log file found"
    fi
}

# Main menu
echo "Select an option:"
echo "1) Show server status"
echo "2) Show WebSocket logs"
echo "3) Show recent errors"
echo "4) Monitor logs in real-time"
echo "5) Show all recent logs"
echo "6) Restart server"
echo "7) Exit"

read -p "Enter choice [1-7]: " choice

case $choice in
    1) show_status ;;
    2) show_websocket_logs ;;
    3) show_errors ;;
    4) monitor_logs ;;
    5) 
        if [ -f "server.log" ]; then
            tail -50 server.log
        else
            echo "No server.log file found"
        fi
        ;;
    6) 
        echo "Restarting server..."
        chmod +x restart_server.sh
        ./restart_server.sh
        ;;
    7) echo "Goodbye!" ;;
    *) echo "Invalid option" ;;
esac
