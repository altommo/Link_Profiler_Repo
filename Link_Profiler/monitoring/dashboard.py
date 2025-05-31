"""
Monitoring Dashboard for Distributed Link Profiler
Simple web interface to monitor queue status and satellites
"""
import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, List
import redis.asyncio as redis
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import uvicorn

app = FastAPI(title="Link Profiler Monitor")
templates = Jinja2Templates(directory="templates")

class MonitoringDashboard:
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_pool = redis.ConnectionPool.from_url(redis_url)
        self.redis = redis.Redis(connection_pool=self.redis_pool)
    
    async def get_queue_metrics(self) -> Dict:
        """Get comprehensive queue metrics"""
        try:
            # Get queue sizes
            job_queue_size = await self.redis.zcard("crawl_jobs")
            result_queue_size = await self.redis.llen("crawl_results")
            
            # Get recent heartbeats (last 5 minutes)
            cutoff = (datetime.now() - timedelta(minutes=5)).timestamp()
            recent_heartbeats = await self.redis.zrangebyscore(
                "crawler_heartbeats_sorted", 
                cutoff, 
                "+inf", 
                withscores=True
            )
            
            # Parse satellite information
            satellites = []
            for heartbeat_data, timestamp in recent_heartbeats:
                try:
                    hb = json.loads(heartbeat_data)
                    hb['last_seen'] = datetime.fromtimestamp(timestamp)
                    satellites.append(hb)
                except json.JSONDecodeError:
                    continue
            
            return {
                "pending_jobs": job_queue_size,
                "results_pending": result_queue_size,
                "active_satellites": len(satellites),
                "satellites": satellites,
                "timestamp": datetime.now()
            }
            
        except Exception as e:
            return {"error": str(e), "timestamp": datetime.now()}
    
    async def get_job_history(self, limit: int = 50) -> List[Dict]:
        """Get recent job completion history"""
        try:
            # This would typically come from your database
            # For now, return mock data
            return [
                {
                    "job_id": f"job-{i:04d}",
                    "status": "completed" if i % 4 != 0 else "failed",
                    "urls_crawled": 100 + (i * 10),
                    "links_found": 50 + (i * 5),
                    "duration_seconds": 300 + (i * 20),
                    "completed_at": datetime.now() - timedelta(minutes=i*5)
                }
                for i in range(limit)
            ]
        except Exception as e:
            return []
    
    async def get_performance_stats(self) -> Dict:
        """Get system performance statistics"""
        try:
            # Get Redis memory usage
            info = await self.redis.info("memory")
            memory_usage = info.get("used_memory_human", "Unknown")
            
            # Calculate throughput (jobs per hour)
            # This would typically come from your job tracking
            
            return {
                "memory_usage": memory_usage,
                "jobs_per_hour": 450,  # Mock data
                "avg_job_duration": 285,  # seconds
                "success_rate": 95.2,  # percentage
                "peak_satellites": 8,
                "current_load": 0.75  # 0-1 scale
            }
            
        except Exception as e:
            return {"error": str(e)}

# Global dashboard instance
dashboard = MonitoringDashboard()

@app.get("/", response_class=HTMLResponse)
async def monitoring_home(request: Request):
    """Main monitoring dashboard"""
    
    # Get all metrics
    queue_metrics = await dashboard.get_queue_metrics()
    job_history = await dashboard.get_job_history(20)
    performance_stats = await dashboard.get_performance_stats()
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "queue_metrics": queue_metrics,
        "job_history": job_history,
        "performance_stats": performance_stats,
        "refresh_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })

@app.get("/api/metrics")
async def get_metrics_api():
    """API endpoint for metrics (for external monitoring)"""
    queue_metrics = await dashboard.get_queue_metrics()
    performance_stats = await dashboard.get_performance_stats()
    
    return {
        **queue_metrics,
        **performance_stats
    }

@app.get("/api/satellites")
async def get_satellites_api():
    """API endpoint for satellite status"""
    metrics = await dashboard.get_queue_metrics()
    return {
        "satellites": metrics.get("satellites", []),
        "active_count": metrics.get("active_satellites", 0)
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        await dashboard.redis.ping()
        return {"status": "healthy", "timestamp": datetime.now().isoformat()}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e), "timestamp": datetime.now().isoformat()}

# CLI tool for queue management
class QueueManager:
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_pool = redis.ConnectionPool.from_url(redis_url)
        self.redis = redis.Redis(connection_pool=self.redis_pool)
    
    async def clear_queue(self, queue_name: str):
        """Clear a specific queue"""
        count = await self.redis.delete(queue_name)
        print(f"Cleared {count} items from {queue_name}")
    
    async def pause_processing(self):
        """Pause job processing by setting a flag"""
        await self.redis.set("processing_paused", "true", ex=3600)  # 1 hour expiry
        print("Job processing paused")
    
    async def resume_processing(self):
        """Resume job processing"""
        await self.redis.delete("processing_paused")
        print("Job processing resumed")
    
    async def get_queue_sizes(self):
        """Get sizes of all queues"""
        jobs = await self.redis.zcard("crawl_jobs")
        results = await self.redis.llen("crawl_results")
        heartbeats = await self.redis.llen("crawler_heartbeats")
        
        print(f"Queue Sizes:")
        print(f"  Jobs: {jobs}")
        print(f"  Results: {results}")
        print(f"  Heartbeats: {heartbeats}")
    
    async def list_satellites(self):
        """List all known satellites"""
        # Get recent heartbeats
        heartbeats = await self.redis.lrange("crawler_heartbeats", 0, -1)
        
        satellites = set()
        for hb_data in heartbeats:
            try:
                hb = json.loads(hb_data)
                satellites.add(hb.get("crawler_id", "unknown"))
            except json.JSONDecodeError:
                continue
        
        print(f"Known Satellites ({len(satellites)}):")
        for sat in sorted(satellites):
            print(f"  - {sat}")

async def cli_main():
    """CLI interface for queue management"""
    import sys
    
    parser = argparse.ArgumentParser(description="Satellite Crawler")
    parser.add_argument("--redis-url", default="redis://localhost:6379", help="Redis connection URL")
    parser.add_argument("--crawler-id", help="Unique crawler identifier")
    parser.add_argument("--region", default="default", help="Crawler region/zone")
    parser.add_argument("--log-level", default="INFO", help="Logging level")
    
    args = parser.parse_args()
    
    # Configure logging
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    if len(sys.argv) < 2:
        print("Usage: python monitoring.py <command>")
        print("Commands:")
        print("  dashboard - Start web dashboard")
        print("  clear-jobs - Clear job queue")
        print("  clear-results - Clear results queue")
        print("  pause - Pause processing")
        print("  resume - Resume processing")
        print("  status - Show queue status")
        print("  satellites - List satellites")
        return
    
    command = sys.argv[1]
    manager = QueueManager()
    
    if command == "dashboard":
        uvicorn.run(app, host="0.0.0.0", port=8001)
    elif command == "clear-jobs":
        await manager.clear_queue("crawl_jobs")
    elif command == "clear-results":
        await manager.clear_queue("crawl_results")
    elif command == "pause":
        await manager.pause_processing()
    elif command == "resume":
        await manager.resume_processing()
    elif command == "status":
        await manager.get_queue_sizes()
    elif command == "satellites":
        await manager.list_satellites()
    else:
        print(f"Unknown command: {command}")

if __name__ == "__main__":
    import argparse # Import argparse here for cli_main
    asyncio.run(cli_main())

# HTML Template (save as templates/dashboard.html)
DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Link Profiler Monitor</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; }
        .card { background: white; padding: 20px; margin: 10px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .metric { display: inline-block; margin: 10px; padding: 15px; background: #e3f2fd; border-radius: 4px; min-width: 150px; text-align: center; }
        .metric h3 { margin: 0 0 5px 0; color: #1976d2; }
        .metric .value { font-size: 24px; font-weight: bold; color: #333; }
        .satellite { background: #f0f8f0; margin: 5px 0; padding: 10px; border-radius: 4px; border-left: 4px solid #4caf50; }
        .satellite.offline { background: #fef0f0; border-left-color: #f44336; }
        .job-row { display: flex; justify-content: space-between; padding: 8px; border-bottom: 1px solid #eee; }
        .status-completed { color: #4caf50; font-weight: bold; }
        .status-failed { color: #f44336; font-weight: bold; }
        .refresh-info { color: #666; font-size: 12px; float: right; }
        h1 { color: #333; }
        h2 { color: #555; border-bottom: 2px solid #ddd; padding-bottom: 5px; }
    </style>
    <script>
        // Auto-refresh every 30 seconds
        setTimeout(() => window.location.reload(), 30000);
    </script>
</head>
<body>
    <div class="container">
        <h1>🔗 Link Profiler Monitor <span class="refresh-info">Last updated: {{ refresh_time }}</span></h1>
        
        <div class="card">
            <h2>📊 Queue Metrics</h2>
            <div class="metric">
                <h3>Pending Jobs</h3>
                <div class="value">{{ queue_metrics.pending_jobs or 0 }}</div>
            </div>
            <div class="metric">
                <h3>Active Satellites</h3>
                <div class="value">{{ queue_metrics.active_satellites or 0 }}</div>
            </div>
            <div class="metric">
                <h3>Results Pending</h3>
                <div class="value">{{ queue_metrics.results_pending or 0 }}</div>
            </div>
            <div class="metric">
                <h3>Success Rate</h3>
                <div class="value">{{ "%.1f"|format(performance_stats.success_rate or 0) }}%</div>
            </div>
        </div>
        
        <div class="card">
            <h2>🛰️ Satellite Crawlers</h2>
            {% if queue_metrics.satellites %}
                {% for satellite in queue_metrics.satellites %}
                <div class="satellite">
                    <strong>{{ satellite.crawler_id }}</strong> 
                    ({{ satellite.region or 'unknown' }})
                    - Last seen: {{ satellite.last_seen.strftime('%H:%M:%S') if satellite.last_seen else 'Never' }}
                    {% if satellite.current_job %}
                    - Processing: {{ satellite.current_job }}
                    {% endif %}
                </div>
                {% endfor %}
            {% else %}
                <p>No active satellites detected</p>
            {% endif %}
        </div>
        
        <div class="card">
            <h2>📈 Recent Jobs</h2>
            {% for job in job_history[:10] %}
            <div class="job-row">
                <span>{{ job.job_id }}</span>
                <span class="status-{{ job.status }}">{{ job.status.upper() }}</span>
                <span>{{ job.urls_crawled }} URLs</span>
                <span>{{ job.links_found }} links</span>
                <span>{{ job.duration_seconds }}s</span>
            </div>
            {% endfor %}
        </div>
    </div>
</body>
</html>
"""

# Save the HTML template
import os
os.makedirs("templates", exist_ok=True)
with open("templates/dashboard.html", "w", encoding="utf-8") as f:
    f.write(DASHBOARD_HTML)
