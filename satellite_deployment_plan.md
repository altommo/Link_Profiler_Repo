# Satellite Crawler Deployment Plan

## Current Infrastructure Overview

You have **6 satellites** already provisioned across strategic locations:

| Satellite ID | Location | IP | Provider | Purpose |
|---|---|---|---|---|
| vps136540-sjo | Buffalo, NY | 107.174.63.73 | CheapWindowsVPS | East Coast Primary |
| vps136542-oeq | Buffalo, NY | 209.54.102.114 | VPSHostingService | East Coast Secondary |  
| vps136545-wbb | Dallas, TX | 198.23.133.150 | VPSPortal | Central US Primary |
| vps136544-092 | Chicago, IL | 23.94.36.140 | VPSPortal | Central US Secondary |
| vps136543-quu | Los Angeles, CA | 107.172.111.138 | VPSHostingService | West Coast Primary |
| vps136541-xq1 | Dublin, IE | 198.55.102.28 | CheapWindowsVPS | European Primary |

**Specs per satellite**: 1GB RAM, 1 Core, 15GB NVMe, Unmetered Traffic

## Phase 1: Master Server Configuration (Week 1)

### 1.1 Master Server Setup
Your master server needs to be accessible by all satellites for Redis coordination.

**Master Server Requirements:**
- **Redis Server** (for job queues, heartbeats, results)
- **PostgreSQL** (for data storage)
- **API Server** (your main Link Profiler application)
- **Mission Control Dashboard** (for monitoring satellites)

**Redis Configuration for Satellite Coordination:**
```yaml
# In your config/config.yaml - update these values
redis:
  url: "redis://YOUR_MASTER_IP:6379/0"
  
queue:
  job_queue_name: "crawl_jobs"
  result_queue_name: "crawl_results"
  heartbeat_queue_sorted_name: "crawler_heartbeats_sorted"
  
satellite:
  heartbeat_interval: 5  # seconds
  job_timeout: 300      # 5 minutes per job
```

### 1.2 Satellite Management Configuration

**Update your Mission Control Service** to track these specific satellite IDs:
```python
# Expected satellite IDs for your fleet
EXPECTED_SATELLITES = [
    "satellite_buffalo_01",  # vps136540-sjo
    "satellite_buffalo_02",  # vps136542-oeq
    "satellite_dallas_01",   # vps136545-wbb
    "satellite_chicago_01",  # vps136544-092
    "satellite_la_01",       # vps136543-quu
    "satellite_dublin_01"    # vps136541-xq1
]
```

## Phase 2: Satellite Deployment (Week 2)

### 2.1 Automated Satellite Setup Script

Using your existing `run_satellite.py`, here's the deployment script:

```bash
#!/bin/bash
# deploy_satellite.sh - Run this on each satellite

# Configuration - passed as arguments
SATELLITE_ID=$1      # e.g., "satellite_buffalo_01" 
MASTER_REDIS_URL=$2  # e.g., "redis://YOUR_MASTER_IP:6379/0"
MASTER_DB_URL=$3     # e.g., "postgresql://user:pass@YOUR_MASTER_IP:5432/linkprofiler"
REGION=$4            # e.g., "us-east", "us-central", "us-west", "eu-west"

echo "🚀 Deploying satellite ${SATELLITE_ID} in region ${REGION}"

# Update system
sudo apt update && sudo apt upgrade -y

# Install Python 3.11 and dependencies
sudo apt install -y python3.11 python3.11-venv python3.11-dev python3-pip git curl wget
sudo apt install -y gcc g++ libnss3 libatk-bridge2.0-0 libdrm-dev libgbm-dev
sudo apt install -y libasound2 libgtk-3-0 libgdk-pixbuf2.0-0 libfontconfig1

# Install Node.js for Lighthouse
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install -y nodejs
sudo npm install -g lighthouse

# Create crawler user and directory
sudo useradd -m -s /bin/bash crawler
sudo mkdir -p /opt/link_profiler
sudo chown crawler:crawler /opt/link_profiler

# Switch to crawler user for installation
sudo -u crawler bash << EOF
cd /opt/link_profiler

# Create Python virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Clone your Link Profiler repository
git clone https://github.com/yourusername/link_profiler.git .
# OR if using private repo:
# git clone https://YOUR_TOKEN@github.com/yourusername/link_profiler.git .

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium
playwright install-deps

# Set environment variables for the satellite
cat > .env << EOL
LP_SATELLITE_ID=${SATELLITE_ID}
LP_REDIS_URL=redis://:redis_secure_pass_456@yspanel.com:6379/0
LP_DATABASE_URL=postgresql://linkprofiler:secure_password_123@yspanel.com:5432/link_profiler_db
LP_SATELLITE_REGION=${REGION}
LP_SATELLITE_HEARTBEAT_INTERVAL=5
LP_CRAWLER_MAX_CONCURRENT_REQUESTS=8
LP_CRAWLER_REQUEST_TIMEOUT=30
LP_ANTI_DETECTION_USER_AGENT_ROTATION=true
LP_ANTI_DETECTION_REQUEST_HEADER_RANDOMIZATION=true
LP_ANTI_DETECTION_HUMAN_LIKE_DELAYS=true
LP_BROWSER_CRAWLER_ENABLED=true
LP_BROWSER_CRAWLER_HEADLESS=true
LP_ACCESS_TOKEN=your_secure_api_token_789
LP_AUTH_SECRET_KEY=cb53bd28ffc37f3f99bcae7b2f23252fc74fe233f623c37b4fbce541c0c672d3
LP_API_EXTERNAL_URL=https://monitor.yspanel.com:8000

# Additional Redis and Database URLs for compatibility
REDIS_URL=redis://:redis_secure_pass_456@yspanel.com:6379/0
DATABASE_URL=postgresql://linkprofiler:secure_password_123@yspanel.com:5432/link_profiler_db
ACCESS_TOKEN=your_secure_api_token_789
EOL

EOF

echo "✅ Satellite ${SATELLITE_ID} setup completed"
```

### 2.2 Systemd Service for Your run_satellite.py

**Create systemd service using your existing script:**
```ini
# /etc/systemd/system/link-profiler-satellite.service
[Unit]
Description=Link Profiler Satellite Crawler
After=network.target

[Service]
Type=simple
User=crawler
Group=crawler
WorkingDirectory=/opt/Link_Profiler_Repo/Link_Profiler
Environment=PATH=/opt/Link_Profiler_Repo/venv/bin
Environment=PYTHONPATH=/opt/Link_Profiler_Repo
EnvironmentFile=/opt/Link_Profiler_Repo/.env
ExecStart=/opt/Link_Profiler_Repo/venv/bin/python /opt/Link_Profiler_Repo/run_satellite.py --redis-url redis://:redis_secure_pass_456@yspanel.com:6379/0 --crawler-id ${LP_SATELLITE_ID} --region ${LP_SATELLITE_REGION} --database-url postgresql://linkprofiler:secure_password_123@yspanel.com:5432/link_profiler_db --log-level INFO
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
KillMode=mixed
KillSignal=SIGTERM
TimeoutStopSec=30

[Install]
WantedBy=multi-user.target
```

### 2.3 Quick Deployment Commands

**Deploy to all satellites with one script (yspanel.com with credentials):**
```bash
#!/bin/bash
# deploy_all_satellites.sh

# Your master server details with actual credentials
MASTER_HOST="yspanel.com"
REDIS_URL="redis://:redis_secure_pass_456@${MASTER_HOST}:6379/0"
DB_URL="postgresql://linkprofiler:secure_password_123@${MASTER_HOST}:5432/link_profiler_db"

# Satellite configurations
declare -A SATELLITES=(
    ["107.174.63.73"]="satellite_buffalo_01:us-east"
    ["209.54.102.114"]="satellite_buffalo_02:us-east"  
    ["198.23.133.150"]="satellite_dallas_01:us-central"
    ["23.94.36.140"]="satellite_chicago_01:us-central"
    ["107.172.111.138"]="satellite_la_01:us-west"
    ["198.55.102.28"]="satellite_dublin_01:eu-west"
)

for IP in "${!SATELLITES[@]}"; do
    IFS=':' read -r SATELLITE_ID REGION <<< "${SATELLITES[$IP]}"
    
    echo "🚀 Deploying to ${SATELLITE_ID} (${IP}) in region ${REGION}"
    
    # Copy deployment script to satellite
    scp deploy_satellite.sh root@${IP}:/tmp/
    
    # Run deployment
    ssh root@${IP} "chmod +x /tmp/deploy_satellite.sh && /tmp/deploy_satellite.sh '${SATELLITE_ID}' '${REDIS_URL}' '${DB_URL}' '${REGION}'"
    
    # Enable and start service
    ssh root@${IP} "systemctl daemon-reload && systemctl enable link-profiler-satellite && systemctl start link-profiler-satellite"
    
    echo "✅ ${SATELLITE_ID} deployed and started"
    sleep 5
done

echo "🎉 All satellites deployed to connect to yspanel.com!"
```

### 2.4 Ready-to-Run Deployment Commands

**Using yspanel.com credentials, deploy each satellite:**

```bash
# Buffalo #1 - vps136540-sjo
scp deploy_satellite.sh root@107.174.63.73:/tmp/
ssh root@107.174.63.73 "/tmp/deploy_satellite.sh 'satellite_buffalo_01' 'redis://:redis_secure_pass_456@yspanel.com:6379/0' 'postgresql://linkprofiler:secure_password_123@yspanel.com:5432/link_profiler_db' 'us-east'"

# Buffalo #2 - vps136542-oeq  
scp deploy_satellite.sh root@209.54.102.114:/tmp/
ssh root@209.54.102.114 "/tmp/deploy_satellite.sh 'satellite_buffalo_02' 'redis://:redis_secure_pass_456@yspanel.com:6379/0' 'postgresql://linkprofiler:secure_password_123@yspanel.com:5432/link_profiler_db' 'us-east'"

# Dallas - vps136545-wbb
scp deploy_satellite.sh root@198.23.133.150:/tmp/
ssh root@198.23.133.150 "/tmp/deploy_satellite.sh 'satellite_dallas_01' 'redis://:redis_secure_pass_456@yspanel.com:6379/0' 'postgresql://linkprofiler:secure_password_123@yspanel.com:5432/link_profiler_db' 'us-central'"

# Chicago - vps136544-092
scp deploy_satellite.sh root@23.94.36.140:/tmp/
ssh root@23.94.36.140 "/tmp/deploy_satellite.sh 'satellite_chicago_01' 'redis://:redis_secure_pass_456@yspanel.com:6379/0' 'postgresql://linkprofiler:secure_password_123@yspanel.com:5432/link_profiler_db' 'us-central'"

# Los Angeles - vps136543-quu
scp deploy_satellite.sh root@107.172.111.138:/tmp/
ssh root@107.172.111.138 "/tmp/deploy_satellite.sh 'satellite_la_01' 'redis://:redis_secure_pass_456@yspanel.com:6379/0' 'postgresql://linkprofiler:secure_password_123@yspanel.com:5432/link_profiler_db' 'us-west'"

# Dublin - vps136541-xq1
scp deploy_satellite.sh root@198.55.102.28:/tmp/
ssh root@198.55.102.28 "/tmp/deploy_satellite.sh 'satellite_dublin_01' 'redis://:redis_secure_pass_456@yspanel.com:6379/0' 'postgresql://linkprofiler:secure_password_123@yspanel.com:5432/link_profiler_db' 'eu-west'"
```

## Phase 3: Initial Data Collection Strategy (Week 3-4)

### 3.1 Seed URL Strategy for 1 Billion Backlinks

**High-Authority Seed Sources:**
```python
# Configure your master server with these seed lists
SEED_URL_SOURCES = {
    "majestic_million": "https://downloads.majestic.com/majestic_million.csv",
    "cisco_umbrella_1m": "http://s3-us-west-1.amazonaws.com/umbrella-static/top-1m.csv",
    "chrome_user_experience": "https://developer.chrome.com/docs/crux/",
    "common_crawl_domains": "https://commoncrawl.org/",
}

# Priority crawling targets
HIGH_PRIORITY_DOMAINS = [
    # News & Media
    "bbc.com", "cnn.com", "reuters.com", "nytimes.com",
    # Tech
    "github.com", "stackoverflow.com", "techcrunch.com",
    # Business
    "forbes.com", "bloomberg.com", "entrepreneur.com",
    # Education
    "harvard.edu", "mit.edu", "stanford.edu",
    # Government
    "gov.uk", "nih.gov", "europa.eu"
]
```

### 3.2 Crawling Job Distribution

**Geographic Job Assignment Logic:**
```python
# In your JobCoordinator, implement smart distribution
REGION_PREFERENCES = {
    "satellite_dublin_01": ["eu", "uk", "de", "fr"],
    "satellite_buffalo_01": ["us", "ca", "com"],
    "satellite_buffalo_02": ["us", "ca", "org"],
    "satellite_dallas_01": ["us", "mx", "net"],
    "satellite_chicago_01": ["us", "ca", "edu"],
    "satellite_la_01": ["us", "asia-pacific", "au"]
}

def assign_crawl_job(target_domain: str) -> str:
    """Assign job to optimal satellite based on geography"""
    if any(tld in target_domain for tld in [".eu", ".uk", ".de", ".fr"]):
        return "satellite_dublin_01"
    elif ".mx" in target_domain:
        return "satellite_dallas_01"
    else:
        # Load balance across US satellites
        return random.choice([
            "satellite_buffalo_01", "satellite_buffalo_02", 
            "satellite_dallas_01", "satellite_chicago_01", 
            "satellite_la_01"
        ])
```

### 3.3 Performance Optimization for 1GB RAM

**Environment Variables for Each Satellite:**
```bash
# Environment variables set via .env file on each satellite
LP_CRAWLER_MAX_CONCURRENT_REQUESTS=8    # Conservative for 1GB RAM
LP_CRAWLER_BATCH_SIZE=50               # URLs per batch  
LP_CRAWLER_MEMORY_LIMIT_MB=800         # Leave 200MB for system
LP_CRAWLER_CACHE_SIZE=1000             # URLs to keep in memory
LP_BROWSER_CRAWLER_MAX_INSTANCES=2     # Only 2 Chrome instances
LP_CRAWLER_REQUEST_DELAY=1.5           # 1.5 seconds between requests
LP_PROXY_ROTATION_ENABLED=false        # Start without proxies
```

### 3.4 Monitoring & Health Checks

**Monitor satellites via your Mission Control Dashboard:**
```bash
# Check satellite status
curl https://yspanel.com/api/mission-control/satellites

# Expected response:
{
  "satellites": [
    {
      "id": "satellite_buffalo_01",
      "status": "active", 
      "last_heartbeat": "2025-01-10T15:30:00Z",
      "jobs_processed": 1547,
      "current_job": null,
      "cpu_usage": 45.2,
      "memory_usage": 78.3,
      "region": "us-east"
    }
  ]
}
```

**Health check script for individual satellites:**
```bash
#!/bin/bash
# health_check_satellite.sh
SATELLITE_IP=$1

echo "🔍 Checking satellite health: ${SATELLITE_IP}"

# Check if service is running
ssh root@${SATELLITE_IP} "systemctl is-active link-profiler-satellite"

# Check logs for errors
ssh root@${SATELLITE_IP} "journalctl -u link-profiler-satellite --since '10 minutes ago' | grep -i error"

# Check resource usage
ssh root@${SATELLITE_IP} "free -h && df -h && top -bn1 | head -20"
```

## Phase 4: Data Collection Execution (Week 3-4)

### 4.1 Start Your 1 Billion Backlink Collection

**Queue initial seed jobs via your API:**
```python
# Script to populate initial crawl jobs
import requests
import json

# Your master server API with credentials
API_BASE = "https://monitor.yspanel.com:8000/api"
API_TOKEN = "your_secure_api_token_789"

# High-priority domains for initial crawling
SEED_DOMAINS = [
    # Top authority sites with lots of outbound links
    "wikipedia.org", "github.com", "stackoverflow.com",
    "reddit.com", "medium.com", "wordpress.org",
    "bbc.com", "cnn.com", "reuters.com",
    "techcrunch.com", "wired.com", "arstechnica.com",
    # Add 1000+ more high-authority domains
]

def submit_crawl_job(domain, job_type="backlink_discovery"):
    """Submit crawl job to master server"""
    payload = {
        "target_url": f"https://{domain}",
        "job_type": job_type,
        "config": {
            "max_depth": 3,
            "max_pages": 1000,
            "extract_images": False,
            "extract_pdfs": False,
            "follow_redirects": True,
            "respect_robots_txt": True
        },
        "priority": 5
    }
    
    response = requests.post(f"{API_BASE}/queue/submit", json=payload)
    if response.status_code == 200:
        print(f"✅ Job submitted for {domain}")
        return response.json()["job_id"]
    else:
        print(f"❌ Failed to submit {domain}: {response.text}")
        return None

# Submit initial batch
print("🚀 Submitting initial crawl jobs...")
for domain in SEED_DOMAINS[:100]:  # Start with first 100
    submit_crawl_job(domain)
    time.sleep(0.1)  # Small delay to avoid overwhelming
```

### 4.2 Expected Performance Metrics

**With 6 satellites running at optimal capacity:**
- **Concurrent requests**: 6 satellites × 8 requests = 48 concurrent crawls
- **Pages per minute**: ~240 pages/minute (5 seconds avg per page)
- **Daily crawling capacity**: ~345,600 pages/day
- **Links discovered**: ~3.4 million links/day (10 links per page average)
- **Time to 1 billion backlinks**: ~290 days at current capacity

**To reach 1 billion faster, consider:**
- Upgrading satellites to 2GB RAM (double concurrency to 16 requests each)
- Adding 6 more satellites (double total capacity)
- Optimizing crawl depth vs breadth for maximum link discovery

### 4.3 Real-Time Progress Tracking

**Monitor progress via Mission Control:**
```bash
# Check current backlink count
curl https://yspanel.com/api/mission-control/metrics | jq '.backlink_discovery_metrics.total_backlinks_discovered'

# Check satellite utilization  
curl https://yspanel.com/api/mission-control/satellites | jq '.satellites[].jobs_completed_24h' | awk '{sum+=$1} END {print "Total jobs completed today:", sum}'
```

## Phase 5: Scaling & Optimization (Week 4+)

### 5.1 Add More Satellites When Ready

**Additional satellite locations to consider:**
- **Asia**: Singapore, Tokyo (for .jp, .sg, .au coverage)
- **South America**: São Paulo (for .br, .ar coverage)  
- **More US regions**: Miami, Seattle, Denver
- **More EU regions**: Frankfurt, Amsterdam, Stockholm

### 5.2 Upgrade Existing Satellites

**Memory upgrade to 2GB per satellite:**
```bash
# Update environment variables for 2GB satellites
LP_CRAWLER_MAX_CONCURRENT_REQUESTS=16  # Double capacity
LP_CRAWLER_MEMORY_LIMIT_MB=1600        # Leave 400MB for system
LP_BROWSER_CRAWLER_MAX_INSTANCES=4     # 4 Chrome instances
```

### 5.3 Database Optimization for Scale

**As you approach millions of backlinks:**
- **Database partitioning** by domain or date
- **Read replicas** for dashboard queries  
- **Redis clustering** for job queue scaling
- **CDN** for static assets and reports