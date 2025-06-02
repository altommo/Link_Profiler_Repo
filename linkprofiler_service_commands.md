# Link Profiler Service Management Commands

## 📋 **Your Link Profiler Services**

Based on your system, you have these services:
- `linkprofiler-api.service` - Main API (Port 8000)
- `linkprofiler-coordinator.service` - Job Coordinator 
- `linkprofiler-monitoring.service` - Monitoring Dashboard (Port 8001)

## 🚀 **Start Commands**

### Start All Services
```bash
sudo systemctl start linkprofiler-api.service linkprofiler-coordinator.service linkprofiler-monitoring.service
```

### Start Individual Services
```bash
# Start API service
sudo systemctl start linkprofiler-api.service

# Start coordinator service  
sudo systemctl start linkprofiler-coordinator.service

# Start monitoring service
sudo systemctl start linkprofiler-monitoring.service
```

## ⏹️ **Stop Commands**

### Stop All Services
```bash
sudo systemctl stop linkprofiler-api.service linkprofiler-coordinator.service linkprofiler-monitoring.service
```

### Stop Individual Services
```bash
# Stop API service
sudo systemctl stop linkprofiler-api.service

# Stop coordinator service
sudo systemctl stop linkprofiler-coordinator.service

# Stop monitoring service
sudo systemctl stop linkprofiler-monitoring.service
```

## 🔄 **Restart Commands**

### Restart All Services
```bash
sudo systemctl restart linkprofiler-api.service linkprofiler-coordinator.service linkprofiler-monitoring.service
```

### Restart Individual Services
```bash
# Restart API service
sudo systemctl restart linkprofiler-api.service

# Restart coordinator service
sudo systemctl restart linkprofiler-coordinator.service

# Restart monitoring service
sudo systemctl restart linkprofiler-monitoring.service
```

## 📊 **Status Check Commands**

### Check All Services Status
```bash
sudo systemctl status linkprofiler-api.service linkprofiler-coordinator.service linkprofiler-monitoring.service --no-pager
```

### Check Individual Service Status
```bash
# Check API service
sudo systemctl status linkprofiler-api.service --no-pager

# Check coordinator service
sudo systemctl status linkprofiler-coordinator.service --no-pager

# Check monitoring service
sudo systemctl status linkprofiler-monitoring.service --no-pager
```

### Quick Status Overview
```bash
# List all Link Profiler services and their status
sudo systemctl list-units --type=service | grep linkprofiler
```

## 🔧 **Configuration Management**

### Reload Service Configurations (after editing service files)
```bash
# Reload systemd daemon
sudo systemctl daemon-reload

# Then restart services
sudo systemctl restart linkprofiler-api.service linkprofiler-coordinator.service linkprofiler-monitoring.service
```

### Enable/Disable Auto-Start on Boot
```bash
# Enable all services to start on boot
sudo systemctl enable linkprofiler-api.service linkprofiler-coordinator.service linkprofiler-monitoring.service

# Disable auto-start on boot
sudo systemctl disable linkprofiler-api.service linkprofiler-coordinator.service linkprofiler-monitoring.service
```

## 📝 **Logging Commands**

### View Recent Logs
```bash
# View logs for all services
sudo journalctl -u linkprofiler-api.service -u linkprofiler-coordinator.service -u linkprofiler-monitoring.service --no-pager -n 20

# View logs for specific service
sudo journalctl -u linkprofiler-api.service --no-pager -n 20

# Follow logs in real-time
sudo journalctl -u linkprofiler-api.service -f
```

### View Logs Since Last Boot
```bash
sudo journalctl -u linkprofiler-api.service --no-pager --since "today"
```

## 🧪 **Health Check Commands**

### Quick Health Check All Services
```bash
echo "=== Link Profiler Services Health Check ==="
echo "API Service (Port 8000):"
curl -s -o /dev/null -w "HTTP Status: %{http_code}\n" https://api.yspanel.com/health

echo "Monitoring Service (Port 8001):"
curl -s -o /dev/null -w "HTTP Status: %{http_code}\n" https://monitor.yspanel.com/health # Changed to /health endpoint

echo "=== Service Status ==="
sudo systemctl is-active linkprofiler-api.service linkprofiler-coordinator.service linkprofiler-monitoring.service
```

### Detailed Health Check
```bash
echo "=== Detailed Health Check ==="
curl -s https://api.yspanel.com/health | jq '.status'
curl -s https://api.yspanel.com/health | jq '.dependencies | keys[]'
```

## 🚨 **Emergency Commands**

### Force Kill and Restart (if services are stuck)
```bash
# Kill all uvicorn/python processes (USE WITH EXTREME CAUTION! This will kill ALL Python processes
# matching the pattern, potentially including unrelated ones. Use only if standard restarts fail.)
sudo pkill -f "uvicorn.*linkprofiler\|python.*Link_Profiler"

# Wait a moment
sleep 5

# Start services again
sudo systemctl start linkprofiler-api.service linkprofiler-coordinator.service linkprofiler-monitoring.service
```

### Full Application Restart
```bash
# Stop all services
sudo systemctl stop linkprofiler-api.service linkprofiler-coordinator.service linkprofiler-monitoring.service

# Reload daemon
sudo systemctl daemon-reload

# Start all services
sudo systemctl start linkprofiler-api.service linkprofiler-coordinator.service linkprofiler-monitoring.service

# Check status
sudo systemctl status linkprofiler-api.service linkprofiler-coordinator.service linkprofiler-monitoring.service --no-pager
```

## 📚 **Useful Aliases (Optional)**

Add these to your `.bashrc` for convenience:
```bash
# Link Profiler service aliases
alias lp-start='sudo systemctl start linkprofiler-api.service linkprofiler-coordinator.service linkprofiler-monitoring.service'
alias lp-stop='sudo systemctl stop linkprofiler-api.service linkprofiler-coordinator.service linkprofiler-monitoring.service'
alias lp-restart='sudo systemctl restart linkprofiler-api.service linkprofiler-coordinator.service linkprofiler-monitoring.service'
alias lp-status='sudo systemctl status linkprofiler-api.service linkprofiler-coordinator.service linkprofiler-monitoring.service --no-pager'
alias lp-logs='sudo journalctl -u linkprofiler-api.service -u linkprofiler-coordinator.service -u linkprofiler-monitoring.service --no-pager -n 20'
alias lp-health='curl -s https://api.yspanel.com/health | jq ".status"'
```

Then reload your shell:
```bash
source ~/.bashrc
```

## 🎯 **Most Common Operations**

### Daily Operations
```bash
# Check if everything is running
lp-status  # (if using aliases) or the full command below
sudo systemctl status linkprofiler-api.service linkprofiler-coordinator.service linkprofiler-monitoring.service --no-pager

# Restart after configuration changes
sudo systemctl restart linkprofiler-api.service linkprofiler-coordinator.service linkprofiler-monitoring.service

# Check health
curl -s https://api.yspanel.com/health | jq '.status'
