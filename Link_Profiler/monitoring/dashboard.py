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
import logging # Added import for logging
import sys
import os

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Link_Profiler.database.database import Database # Import Database
from Link_Profiler.core.models import CrawlJob, CrawlStatus # Import CrawlJob model and CrawlStatus
from Link_Profiler.config.config_loader import config_loader # Import config_loader

app = FastAPI(title="Link Profiler Monitor")
templates = Jinja2Templates(directory="templates")

class MonitoringDashboard:
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_pool = redis.ConnectionPool.from_url(redis_url)
        self.redis = redis.Redis(connection_pool=self.redis_pool)
        self.db = Database() # Initialize database connection for job history
        self.performance_window_seconds = config_loader.get("monitoring.performance_window", 3600) # Default to 1 hour

    async def get_queue_metrics(self) -> Dict:
        """Get comprehensive queue metrics"""
        try:
            # Get queue sizes
            job_queue_size = await self.redis.zcard("crawl_jobs")
            result_queue_size = await self.redis.llen("crawl_results")
            
            # Get recent heartbeats (last 5 minutes) from the sorted set
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
                    logging.warning(f"Failed to decode heartbeat data: {heartbeat_data}")
                    continue
            
            return {
                "pending_jobs": job_queue_size,
                "results_pending": result_queue_size,
                "active_satellites": len(satellites),
                "satellites": satellites,
                "timestamp": datetime.now()
            }
            
        except Exception as e:
            logging.error(f"Error getting queue metrics: {e}", exc_info=True)
            return {"error": str(e), "timestamp": datetime.now()}
    
    async def get_job_history(self, limit: int = 50) -> List[Dict]:
        """Get recent job completion history from the database."""
        try:
            # Fetch all jobs from the database
            all_jobs = self.db.get_all_crawl_jobs()
            
            # Filter for completed/failed jobs and sort by completion date
            completed_jobs = sorted(
                [job for job in all_jobs if job.is_completed],
                key=lambda job: job.completed_date if job.completed_date else datetime.min,
                reverse=True
            )
            
            # Prepare data for display
            history_data = []
            for job in completed_jobs[:limit]:
                history_data.append({
                    "job_id": job.id,
                    "status": job.status.value,
                    "urls_crawled": job.urls_crawled,
                    "links_found": job.links_found,
                    "duration_seconds": round(job.duration_seconds, 2) if job.duration_seconds is not None else "N/A",
                    "completed_at": job.completed_date.strftime("%Y-%m-%d %H:%M:%S") if job.completed_date else "N/A"
                })
            return history_data
        except Exception as e:
            logging.error(f"Error getting job history: {e}", exc_info=True)
            return []
    
    async def get_performance_stats(self) -> Dict:
        """
        Get system performance statistics based on historical job data.
        Calculates jobs per hour, average job duration, and success rate.
        """
        try:
            # Get Redis memory usage
            info = await self.redis.info("memory")
            memory_usage = info.get("used_memory_human", "Unknown")
            
            # Calculate throughput and success rate based on real data
            cutoff_time = datetime.now() - timedelta(seconds=self.performance_window_seconds)
            
            all_jobs = self.db.get_all_crawl_jobs() # Fetch all jobs
            
            recent_completed_jobs = [
                job for job in all_jobs 
                if job.is_completed and job.completed_date and job.completed_date >= cutoff_time
            ]
            
            total_jobs_in_window = len(recent_completed_jobs)
            successful_jobs_in_window = len([job for job in recent_completed_jobs if job.status == CrawlStatus.COMPLETED])
            failed_jobs_in_window = total_jobs_in_window - successful_jobs_in_window

            jobs_per_hour = 0.0
            avg_job_duration = 0.0
            success_rate = 0.0

            if total_jobs_in_window > 0:
                # Convert window to hours for jobs_per_hour calculation
                window_hours = self.performance_window_seconds / 3600
                jobs_per_hour = total_jobs_in_window / window_hours
                
                # Calculate average duration for successful jobs
                successful_durations = [job.duration_seconds for job in recent_completed_jobs if job.status == CrawlStatus.COMPLETED and job.duration_seconds is not None]
                if successful_durations:
                    avg_job_duration = sum(successful_durations) / len(successful_durations)
                
                success_rate = (successful_jobs_in_window / total_jobs_in_window) * 100
            
            queue_metrics = await self.get_queue_metrics()
            active_satellites = queue_metrics.get("active_satellites", 0)
            pending_jobs = queue_metrics.get("pending_jobs", 0)

            # Calculate current load: ratio of pending jobs to active satellites
            # If no active satellites, load is undefined or very high if jobs are pending
            current_load = 0.0
            if active_satellites > 0:
                current_load = min(1.0, pending_jobs / (active_satellites * 10)) # Arbitrary scaling factor (e.g., 10 jobs per satellite)
            elif pending_jobs > 0:
                current_load = 1.0 # High load if jobs are pending but no satellites
            
            return {
                "memory_usage": memory_usage,
                "jobs_per_hour": round(jobs_per_hour, 2),
                "avg_job_duration": round(avg_job_duration, 2),
                "success_rate": round(success_rate, 1),
                "peak_satellites": active_satellites, # Using current active as a proxy for peak for now
                "current_load": round(current_load, 2)
            }
            
        except Exception as e:
            logging.error(f"Error getting performance stats: {e}", exc_info=True)
            return {"error": str(e)}

# Global dashboard instance
dashboard = MonitoringDashboard()

@app.get("/", response_class=HTMLResponse)
async def monitoring_home(request: Request):
    """Main monitoring dashboard"""
    
    # Get all metrics
    queue_metrics = await dashboard.get_queue_metrics()
    job_history = await dashboard.get_job_history(config_loader.get("monitoring.max_job_history", 50))
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
        # Use the sorted set for heartbeats
        heartbeats_count = await self.redis.zcard("crawler_heartbeats_sorted")
        
        print(f"Queue Sizes:")
        print(f"  Jobs: {jobs}")
        print(f"  Results: {results}")
        print(f"  Heartbeats (active satellites): {heartbeats_count}")
    
    async def list_satellites(self):
        """List all known satellites"""
        # Get recent heartbeats from the sorted set
        cutoff = (datetime.now() - timedelta(minutes=5)).timestamp()
        recent_heartbeats = await self.redis.zrangebyscore(
            "crawler_heartbeats_sorted", 
            cutoff, 
            "+inf", 
            withscores=True
        )
        
        satellites = set()
        for heartbeat_data, timestamp in recent_heartbeats:
            try:
                hb = json.loads(heartbeat_data)
                satellites.add(hb.get("crawler_id", "unknown"))
            except json.JSONDecodeError:
                logging.warning(f"Failed to decode heartbeat data in list_satellites: {heartbeat_data}")
                continue
        
        print(f"Known Active Satellites ({len(satellites)}):")
        if satellites:
            for sat in sorted(list(satellites)):
                print(f"  - {sat}")
        else:
            print("  No active satellites detected in the last 5 minutes.")

async def cli_main():
    """CLI interface for queue management"""
    import argparse # Import argparse here for cli_main
    
    parser = argparse.ArgumentParser(description="Link Profiler Monitoring CLI")
    parser.add_argument("--redis-url", default="redis://localhost:6379", help="Redis connection URL")
    parser.add_argument("--log-level", default="INFO", help="Logging level")
    
    # Subparsers for commands
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Dashboard command
    dashboard_parser = subparsers.add_parser("dashboard", help="Start the web monitoring dashboard")

    # Clear queues commands
    clear_jobs_parser = subparsers.add_parser("clear-jobs", help="Clear the job queue")
    clear_results_parser = subparsers.add_parser("clear-results", help="Clear the results queue")
    clear_dead_letters_parser = subparsers.add_parser("clear-dead-letters", help="Clear the dead-letter queue")

    # Pause/Resume commands
    pause_parser = subparsers.add_parser("pause", help="Pause job processing")
    resume_parser = subparsers.add_parser("resume", help="Resume job processing")

    # Status commands
    status_parser = subparsers.add_parser("status", help="Show queue status")
    satellites_parser = subparsers.add_parser("satellites", help="List active satellites")
    
    args = parser.parse_args()
    
    # Configure logging
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    manager = QueueManager(redis_url=args.redis_url)
    
    if args.command == "dashboard":
        uvicorn.run(app, host="0.0.0.0", port=8001)
    elif args.command == "clear-jobs":
        await manager.clear_queue("crawl_jobs")
    elif args.command == "clear-results":
        await manager.clear_queue("crawl_results")
    elif args.command == "clear-dead-letters":
        await manager.clear_queue(os.getenv("DEAD_LETTER_QUEUE_NAME", "dead_letter_queue"))
    elif args.command == "pause":
        await manager.pause_processing()
    elif args.command == "resume":
        await manager.resume_processing()
    elif args.command == "status":
        await manager.get_queue_sizes()
    elif args.command == "satellites":
        await manager.list_satellites()
    else:
        parser.print_help()

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
