#!/bin/bash

echo "======================================"
echo "Server Status Check"
echo "======================================"

echo "1. Checking if FastAPI/uvicorn is running..."
if pgrep -f "uvicorn.*main:app" > /dev/null; then
    echo "✅ uvicorn process found:"
    ps aux | grep "uvicorn.*main:app" | grep -v grep
else
    echo "❌ No uvicorn process running"
fi

echo
echo "2. Checking port 8000..."
if netstat -tlnp | grep ":8000" > /dev/null; then
    echo "✅ Something is listening on port 8000:"
    netstat -tlnp | grep ":8000"
else
    echo "❌ Nothing listening on port 8000"
fi

echo
echo "3. Checking nginx status..."
if systemctl is-active nginx > /dev/null; then
    echo "✅ nginx is running"
else
    echo "❌ nginx is not running"
fi

echo
echo "4. Checking nginx configuration for backend..."
if grep -r "proxy_pass.*8000" /etc/nginx/ > /dev/null 2>&1; then
    echo "✅ nginx is configured to proxy to port 8000"
    grep -r "proxy_pass.*8000" /etc/nginx/ 2>/dev/null
else
    echo "❌ nginx proxy configuration not found"
fi

echo
echo "5. Recent nginx error logs..."
if [ -f /var/log/nginx/error.log ]; then
    echo "Last 5 lines from nginx error log:"
    tail -5 /var/log/nginx/error.log
else
    echo "No nginx error log found"
fi

echo
echo "6. Checking if we're in the right directory..."
pwd
ls -la main.py 2>/dev/null || echo "❌ main.py not found in current directory"

echo
echo "7. Checking Python virtual environment..."
if [ -n "$VIRTUAL_ENV" ]; then
    echo "✅ Virtual environment active: $VIRTUAL_ENV"
else
    echo "⚠️ No virtual environment detected"
fi
