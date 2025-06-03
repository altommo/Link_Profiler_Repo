#!/bin/bash

# Link Profiler Deployment Script
# This script updates the systemd service files and restarts services

echo "=== Link Profiler Deployment Script ==="

# Step 1: Copy systemd service files to /etc/systemd/system/
echo "1. Copying systemd service files..."
sudo cp /opt/Link_Profiler_Repo/etc/systemd/system/linkprofiler-api.service /etc/systemd/system/
sudo cp /opt/Link_Profiler_Repo/etc/systemd/system/linkprofiler-coordinator.service /etc/systemd/system/
sudo cp /opt/Link_Profiler_Repo/etc/systemd/system/linkprofiler-monitoring.service /etc/systemd/system/

# Step 2: Reload systemd
echo "2. Reloading systemd daemon..."
sudo systemctl daemon-reload

# Step 3: Register monitor user (if main API is running)
echo "3. Registering monitor user..."
sleep 2
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "monitor_user",
    "email": "monitor@example.com",
    "password": "monitor_secure_password_123"
  }' || echo "Monitor user registration failed (user may already exist)"

# Step 4: Restart services in correct order
echo "4. Restarting services..."
sudo systemctl restart linkprofiler-api
echo "Waiting for API to start..."
sleep 10

sudo systemctl restart linkprofiler-coordinator
echo "Waiting for coordinator to start..."
sleep 5

sudo systemctl restart linkprofiler-monitoring
echo "Waiting for monitoring to start..."
sleep 5

# Step 5: Check service status
echo "5. Checking service status..."
sudo systemctl status linkprofiler-api --no-pager -l
sudo systemctl status linkprofiler-coordinator --no-pager -l
sudo systemctl status linkprofiler-monitoring --no-pager -l

echo "=== Deployment Complete ==="
echo "Dashboard should be available at: https://monitor.yspanel.com:8001"
echo "API should be available at: https://monitor.yspanel.com:8000"

# Step 6: Show recent logs
echo "6. Recent monitoring logs:"
sudo journalctl -u linkprofiler-monitoring -n 10 --no-pager
