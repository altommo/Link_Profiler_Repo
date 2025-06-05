# 🚀 Queue System Documentation

## Overview

The Link Profiler now includes a **distributed queue system** that allows you to scale crawling operations across multiple satellite servers. This system uses Redis for job distribution and coordination.

## 📋 Quick Start

### 1. Prerequisites
```bash
# Install Redis
# Ubuntu/Debian: sudo apt install redis-server
# macOS: brew install redis
# Windows: Use Docker or WSL

# Install Python dependencies
pip install -r requirements.txt
```

### 2. Start Redis
```bash
redis-server
```

### 3. Start the System

**Option A: All-in-One (Development)**
```bash
# Windows
Link_Profiler\scripts\start_local.bat

# Linux/macOS
chmod +x Link_Profiler/scripts/start_local.sh
./Link_Profiler/scripts/start_local.sh
```

**Option B: Individual Components**
```bash
# Terminal 1: Start coordinator
python run_coordinator.py

# Terminal 2: Start satellite crawler
python run_satellite.py --region us-east-1

# Terminal 3: Start main API with queue endpoints
python -m Link_Profiler.api.main_with_queue

# Terminal 4: Start monitoring dashboard
python -m Link_Profiler.monitoring.dashboard dashboard
```

### 4. Test the System
```bash
# Test queue functionality
python tests/test_queue.py

# Submit a test job via API
curl -X POST "http://localhost:8000/queue/submit_crawl" \
     -H "Content-Type: application/json" \
     -d '{
       "target_url": "https://example.com",
       "initial_seed_urls": ["https://competitor.com"],
       "priority": 5
     }'
```

## 🌐 API Endpoints

### Queue Management
- `POST /queue/submit_crawl` - Submit crawl job to queue
- `GET /queue/job_status/{job_id}` - Get job status
- `GET /queue/stats` - Get queue statistics
- `GET /queue/manage/crawler_health` - Get satellite health

### Traditional Endpoints (Still Available)
- `POST /crawl/start_backlink_discovery` - Direct crawl (non-queued)
- `GET /crawl/status/{job_id}` - Get direct crawl status
- All existing domain and backlink endpoints

## 🐳 Production Deployment

### Docker Compose (Recommended)
```bash
cd Link_Profiler/deployment/docker
chmod +x deploy.sh
./deploy.sh

# Scale satellites
./scale-satellites.sh 10
```

### Kubernetes
```bash
cd Link_Profiler/deployment/kubernetes
chmod +x k8s-deploy.sh
./k8s-deploy.sh

# Scale satellites
kubectl scale deployment satellite-crawlers --replicas=15 -n link-profiler
```

### Manual Satellite Deployment
```bash
# On satellite server
python run_satellite.py \
  --redis-url redis://main-server:6379 \
  --region eu-west-1 \
  --crawler-id satellite-eu-01
```

## 📊 Monitoring

### Web Dashboard
- **URL**: http://localhost:8001
- **Features**: Real-time queue stats, satellite health, job history

### API Monitoring
```bash
# Queue statistics
curl http://localhost:8000/queue/stats

# Crawler health
curl http://localhost:8000/queue/manage/crawler_health
```

### CLI Tools
```bash
# Check queue status
python -m Link_Profiler.monitoring.dashboard status

# List active satellites
python -m Link_Profiler.monitoring.dashboard satellites

# Clear job queue (emergency)
python -m Link_Profiler.monitoring.dashboard clear-jobs
```

## ⚙️ Configuration

### Environment Variables
Create `.env` file based on `.env.example`:
```bash
REDIS_URL=redis://localhost:6379
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/link_profiler_db
MAX_SATELLITES=10
LOG_LEVEL=INFO
```

### Configuration Files
- `config/default.json` - Default settings
- `config/development.json` - Development overrides
- `config/production.json` - Production settings

## 🔧 Architecture

### Components
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Main Server   │    │     Redis       │    │   Satellite     │
│                 │    │   (Job Queue)   │    │   Crawlers      │
│ • API Server    │◄──►│                 │◄──►│                 │
│ • Job Coord.    │    │ • Jobs Queue    │    │ • Web Crawler   │
│ • Database      │    │ • Results Queue │    │ • Link Extract  │
│ • Monitoring    │    │ • Heartbeats    │    │ • Lightweight   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### Data Flow
1. **Job Submission**: API receives crawl request → Job Coordinator → Redis Queue
2. **Job Processing**: Satellite pulls job → Crawls URLs → Sends results back
3. **Result Processing**: Coordinator processes results → Updates database → Notifies API

## 🚀 Scaling Guide

### Horizontal Scaling
```bash
# Add more satellites
docker-compose up -d --scale satellite-1=20

# Or deploy to different servers
python run_satellite.py --redis-url redis://main-server:6379 --region asia-1
```

### Performance Tuning
```json
{
  "crawler": {
    "max_pages": 5000,
    "delay_seconds": 0.5,
    "timeout_seconds": 20
  },
  "queue": {
    "max_retries": 3,
    "heartbeat_interval": 30
  }
}
```

### Geographic Distribution
```bash
# US East
python run_satellite.py --region us-east-1 --redis-url redis://main:6379

# Europe
python run_satellite.py --region eu-west-1 --redis-url redis://main:6379

# Asia
python run_satellite.py --region asia-1 --redis-url redis://main:6379
```

## 🔍 Troubleshooting

### Common Issues

**Redis Connection Failed**
```bash
# Check Redis status
redis-cli ping

# Start Redis if not running
redis-server
```

**Satellites Not Appearing**
```bash
# Check heartbeats
redis-cli llen crawler_heartbeats

# Check satellite logs
python run_satellite.py --log-level DEBUG
```

**Queue Stuck**
```bash
# Check queue size
redis-cli zcard crawl_jobs

# Clear stuck jobs (emergency)
python -m Link_Profiler.monitoring.dashboard clear-jobs
```

### Logs and Debugging
```bash
# Coordinator logs
python run_coordinator.py --log-level DEBUG

# Satellite logs
python run_satellite.py --log-level DEBUG

# API logs (check console output)
python -m Link_Profiler.api.main_with_queue
```

## 📈 Performance Expectations

| Satellites | URLs/min | Memory | CPU Usage |
|-----------|----------|--------|-----------|
| 1         | 100-200  | ~50MB  | ~10%      |
| 5         | 500-1000 | ~250MB | ~30%      |
| 10        | 1-2K     | ~500MB | ~50%      |
| 20        | 2-4K     | ~1GB   | ~80%      |

## 🔐 Security Considerations

### Redis Security
```bash
# Set Redis password
redis-cli CONFIG SET requirepass "your-password"

# Update REDIS_URL
REDIS_URL=redis://:your-password@localhost:6379
```

### Network Security
- Use private networks for satellite communication
- Implement Redis AUTH for production
- Consider Redis SSL/TLS for sensitive environments

## 🎯 Example Use Cases

### 1. Large-Scale Backlink Discovery
```python
# Submit 1000 URLs for comprehensive backlink analysis
for target_url in target_urls:
    requests.post("http://localhost:8000/queue/submit_crawl", json={
        "target_url": target_url,
        "initial_seed_urls": competitor_urls,
        "priority": 8,
        "config": {"max_pages": 5000}
    })
```

### 2. Geographic SEO Analysis
```bash
# Deploy region-specific satellites
python run_satellite.py --region us-east-1 --crawler-id seo-us-01
python run_satellite.py --region eu-west-1 --crawler-id seo-eu-01
```

### 3. Competitor Monitoring
```python
# Continuous monitoring with priority queuing
high_priority_targets = ["competitor1.com", "competitor2.com"]
for target in high_priority_targets:
    submit_crawl_job(target, priority=10)
```

This queue system transforms Link Profiler from a single-server tool into a **distributed, scalable crawling platform** capable of handling enterprise-level workloads! 🚀
