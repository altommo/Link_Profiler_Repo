# Link Profiler Deployment - Changes Summary

## Files Modified & Created

### 1. `/opt/Link_Profiler_Repo/Link_Profiler/main.py`
**Issue**: `sys.sys.path.insert(0, project_root)` should be `sys.path.insert(0, project_root)`

**Fix Applied**:
```bash
cd /opt/Link_Profiler_Repo/Link_Profiler
sed -i 's/sys.sys.path.insert/sys.path.insert/g' main.py
```

### 2. `/opt/Link_Profiler_Repo/Link_Profiler/queue_system/job_coordinator.py`
**Issues**: 
- Database initialized without URL parameter (defaulted to postgres user)
- Redis URL hardcoded to `redis://localhost:6379` (no password)

**Fixes Applied**:

#### Database Fix:
```python
# BEFORE:
db_instance = Database()

# AFTER:
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://linkprofiler:secure_password_123@localhost:5432/link_profiler_db')
db_instance = Database(db_url=DATABASE_URL)
```

#### Redis Fix:
```python
# BEFORE:
def __init__(self, redis_url: str = "redis://localhost:6379", ...):
    self.redis_pool = redis.ConnectionPool.from_url(redis_url)

# AFTER:
def __init__(self, redis_url: str = None, ...):
    redis_url = redis_url or os.getenv("REDIS_URL", "redis://:redis_secure_pass_456@127.0.0.1:6379/0")
    self.redis_pool = redis.ConnectionPool.from_url(redis_url)
```

#### Environment Import:
```python
# Added at top of file:
import os
```

### 3. `/opt/Link_Profiler_Repo/Link_Profiler/config/default.json`
**Issue**: Config file was missing

**Fix Applied**:
```bash
mkdir -p /opt/Link_Profiler_Repo/Link_Profiler/config
cat > /opt/Link_Profiler_Repo/Link_Profiler/config/default.json << 'EOF'
{
  "database": {
    "url": "postgresql://linkprofiler:secure_password_123@localhost:5432/link_profiler_db"
  },
  "redis": {
    "url": "redis://:redis_secure_pass_456@127.0.0.1:6379/0"
  },
  "api": {
    "port": 8000,
    "access_token": "your_secure_api_token_789"
  }
}
EOF
```

### 4. `/etc/systemd/system/linkprofiler-api.service`
**Issues**: Missing environment variables and Python path

**Fix Applied**:
```ini
[Unit]
Description=Link Profiler API
After=network.target postgresql.service redis.service

[Service]
Type=simple
User=root
WorkingDirectory=/opt/Link_Profiler_Repo/Link_Profiler
Environment=PATH=/opt/Link_Profiler_Repo/venv/bin
Environment=PYTHONPATH=/opt/Link_Profiler_Repo
Environment=LP_DATABASE_URL=postgresql://linkprofiler:secure_password_123@localhost:5432/link_profiler_db
Environment=DATABASE_URL=postgresql://linkprofiler:secure_password_123@localhost:5432/link_profiler_db
Environment=LP_REDIS_URL=redis://:redis_secure_pass_456@127.0.0.1:6379/0
Environment=REDIS_URL=redis://:redis_secure_pass_456@127.0.0.1:6379/0
Environment=ACCESS_TOKEN=your_secure_api_token_789
Environment=LP_ACCESS_TOKEN=your_secure_api_token_789
ExecStart=/opt/Link_Profiler_Repo/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 5. `/etc/systemd/system/linkprofiler-coordinator.service`
**Issues**: Missing environment variables and Python path

**Fix Applied**:
```ini
[Unit]
Description=Link Profiler Job Coordinator
After=network.target redis.service postgresql.service

[Service]
Type=simple
User=root
WorkingDirectory=/opt/Link_Profiler_Repo
Environment=PATH=/opt/Link_Profiler_Repo/venv/bin
Environment=PYTHONPATH=/opt/Link_Profiler_Repo
Environment=LP_DATABASE_URL=postgresql://linkprofiler:secure_password_123@localhost:5432/link_profiler_db
Environment=DATABASE_URL=postgresql://linkprofiler:secure_password_123@localhost:5432/link_profiler_db
Environment=LP_REDIS_URL=redis://:redis_secure_pass_456@127.0.0.1:6379/0
Environment=REDIS_URL=redis://:redis_secure_pass_456@127.0.0.1:6379/0
Environment=ACCESS_TOKEN=your_secure_api_token_789
Environment=LP_ACCESS_TOKEN=your_secure_api_token_789
Environment=JWT_SECRET_KEY=your_super_secret_jwt_key_987654321
ExecStart=/opt/Link_Profiler_Repo/venv/bin/python Link_Profiler/queue_system/job_coordinator.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 6. `/etc/systemd/system/linkprofiler-monitoring.service` (NEW)
**Issue**: Monitoring dashboard needed to be created

**Fix Applied**:
```ini
[Unit]
Description=Link Profiler Monitoring Dashboard
After=network.target linkprofiler-api.service

[Service]
Type=simple
User=root
WorkingDirectory=/opt/Link_Profiler_Repo/Link_Profiler/monitoring
Environment=PATH=/opt/Link_Profiler_Repo/venv/bin
Environment=PYTHONPATH=/opt/Link_Profiler_Repo
Environment=LP_DATABASE_URL=postgresql://linkprofiler:secure_password_123@localhost:5432/link_profiler_db
Environment=DATABASE_URL=postgresql://linkprofiler:secure_password_123@localhost:5432/link_profiler_db
Environment=LP_REDIS_URL=redis://:redis_secure_pass_456@127.0.0.1:6379/0
Environment=REDIS_URL=redis://:redis_secure_pass_456@127.0.0.1:6379/0
ExecStart=/opt/Link_Profiler_Repo/venv/bin/uvicorn dashboard:app --host 0.0.0.0 --port 8001
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 7. `/etc/nginx/sites-available/linkprofiler` (UPDATED - CRITICAL)
**Issue**: All domains including monitor.yspanel.com were proxying to port 8000 instead of monitoring dashboard on port 8001

**⚠️ CRITICAL FIX - Conditional Routing Applied**:
```nginx
# BEFORE: All traffic went to port 8000
location / {
    proxy_pass http://127.0.0.1:8000;
    # ... other config
}

# AFTER: Conditional routing based on domain
location / {
    if ($host = monitor.yspanel.com) {
        proxy_pass http://127.0.0.1:8001;
    }
    if ($host != monitor.yspanel.com) {
        proxy_pass http://127.0.0.1:8000;
    }
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-Host $server_name;
    # WebSocket support
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    # Timeouts
    proxy_connect_timeout 60s;
    proxy_send_timeout 60s;
    proxy_read_timeout 60s;
}
```

**⚠️ NGINX PITFALL WARNING**:
Using `if` statements in nginx location blocks can be problematic and is generally discouraged. The cleaner approach would be separate server blocks, but conditional routing was implemented for simplicity. Monitor for any nginx issues.

## Dependencies Installed

```bash
# Missing Python packages
pip install setuptools pkg_resources redis psycopg2-binary python-dotenv

# Playwright reinstall
pip install --upgrade playwright
playwright install chromium
```

## Database Permissions

```bash
# Ensured linkprofiler user has correct permissions
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE link_profiler_db TO linkprofiler;"
```

## Key Environment Variables Used

```bash
# Database
DATABASE_URL=postgresql://linkprofiler:secure_password_123@localhost:5432/link_profiler_db
LP_DATABASE_URL=postgresql://linkprofiler:secure_password_123@localhost:5432/link_profiler_db

# Redis
REDIS_URL=redis://:redis_secure_pass_456@127.0.0.1:6379/0
LP_REDIS_URL=redis://:redis_secure_pass_456@127.0.0.1:6379/0

# API Security
ACCESS_TOKEN=your_secure_api_token_789
LP_ACCESS_TOKEN=your_secure_api_token_789
JWT_SECRET_KEY=your_super_secret_jwt_key_987654321

# Python Path
PYTHONPATH=/opt/Link_Profiler_Repo
```

## Critical Pitfalls & Warnings

### ⚠️ **NGINX CONDITIONAL ROUTING PITFALL**
**Issue**: Using `if` statements in nginx location blocks can cause unexpected behavior
**Current Implementation**: 
```nginx
location / {
    if ($host = monitor.yspanel.com) {
        proxy_pass http://127.0.0.1:8001;
    }
    if ($host != monitor.yspanel.com) {
        proxy_pass http://127.0.0.1:8000;
    }
    # ... rest of config
}
```

**Potential Problems**:
- Nginx `if` is evil - can cause unpredictable behavior
- Performance impact with multiple conditionals
- May break with complex location matching

**Recommended Future Fix** (Separate Server Blocks):
```nginx
# Dedicated server block for monitor.yspanel.com
server {
    listen 443 ssl http2;
    server_name monitor.yspanel.com;
    location / {
        proxy_pass http://127.0.0.1:8001;
    }
}

# Main server block for other domains
server {
    listen 443 ssl http2; 
    server_name api.yspanel.com linkprofiler.yspanel.com admin.yspanel.com ws.yspanel.com status.yspanel.com;
    location / {
        proxy_pass http://127.0.0.1:8000;
    }
}
```

### ⚠️ **CONFIG SYSTEM DEPENDENCY**
**Issue**: Monitoring dashboard relies on config system working correctly
**Pitfall**: If config loader fails, services fall back to hardcoded defaults (postgres user)
**Mitigation**: Always verify environment variables are loaded correctly

### ⚠️ **SERVICE STARTUP ORDER**
**Critical Dependencies**:
1. PostgreSQL must start first
2. Redis must start first  
3. API service before monitoring
4. Coordinator after database is ready

**Pitfall**: If services start out of order, authentication will fail

### ⚠️ **SSL CERTIFICATE COVERAGE**
**Issue**: All subdomains must be included in SSL certificate
**Current Certificate Must Include**:
- yspanel.com
- www.yspanel.com  
- api.yspanel.com
- linkprofiler.yspanel.com
- admin.yspanel.com
- ws.yspanel.com
- monitor.yspanel.com
- status.yspanel.com

**Pitfall**: Adding new subdomains requires certificate renewal

### ⚠️ **HARDCODED CREDENTIALS IN FALLBACKS**
**Issue**: Some fallback values still contain hardcoded credentials
**Locations to Monitor**:
- Database class defaults to `postgres:postgres`
- Redis defaults to `localhost:6379` (no auth)
- Config system fallbacks

**Recommendation**: Remove all hardcoded fallbacks and force explicit configuration

## Root Causes Fixed

1. **Code Bug**: `sys.sys.path` typo in main.py
2. **Missing Dependencies**: setuptools, redis, psycopg2-binary
3. **Environment Variables**: Services weren't loading database/redis URLs
4. **Python Path**: coordinator couldn't find Link_Profiler module
5. **Default Parameters**: Database and Redis classes using wrong defaults
6. **Service Configuration**: systemd services missing proper environment setup

## Final System State

✅ **API Service**: Running on port 8000, accessible via https://api.yspanel.com  
✅ **Coordinator Service**: Running with all processing loops active  
✅ **Monitoring Dashboard**: Running on port 8001, accessible via https://monitor.yspanel.com  
✅ **Database**: Connected using linkprofiler user  
✅ **Redis**: Connected with authentication  
✅ **Nginx**: Proxying HTTPS requests correctly with conditional routing  
✅ **SSL**: Certificates working for all subdomains  

## Complete Working URL List

### **✅ Main API Endpoints:**
- **https://api.yspanel.com** - Primary API endpoint
- **https://linkprofiler.yspanel.com** - Alternative API endpoint
- **https://admin.yspanel.com** - Admin functionality 
- **https://ws.yspanel.com** - WebSocket connections

### **✅ Documentation & Monitoring:**
- **https://api.yspanel.com/docs** - Interactive API documentation
- **https://linkprofiler.yspanel.com/docs** - Same docs (alternative URL)
- **https://monitor.yspanel.com** - Live monitoring dashboard
- **https://status.yspanel.com** - Status endpoints (if implemented)

### **✅ Health & System:**
- **https://api.yspanel.com/health** - System health check
- **https://api.yspanel.com/status** - API status (if implemented)
- **https://api.yspanel.com/metrics** - Prometheus metrics (if implemented)

### **✅ Main Sites:**
- **https://yspanel.com** - Your main domain
- **https://www.yspanel.com** - Your www domain

## Services Status

### **Running Services:**
```bash
systemctl status linkprofiler-api linkprofiler-coordinator linkprofiler-monitoring
```

### **Port Usage:**
- **Port 8000**: Main Link Profiler API
- **Port 8001**: Monitoring Dashboard  
- **Port 80/443**: Nginx proxy
- **Port 5432**: PostgreSQL
- **Port 6379**: Redis

## Next Phase: Satellite Deployment

The main node is now ready for satellite deployment to the 6 VPS servers:
- Buffalo1: 107.174.63.73 (vps136540-sjo)
- Buffalo2: 209.54.102.114 (vps136542-oeq)
- Dallas: 198.23.133.150 (vps136545-wbb)
- Chicago: 23.94.36.140 (vps136544-092)
- Los Angeles: 107.172.111.138 (vps136543-quu)
- Dublin: 198.55.102.28 (vps136541-xq1)

All changes are complete and the system is fully operational with monitoring dashboard!