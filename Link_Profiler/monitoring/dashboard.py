"""
Monitoring Dashboard for Distributed Link Profiler
Simple web interface to monitor queue status and satellites
"""
import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any
import redis.asyncio as redis
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import uvicorn
import logging
import sys
import os

# Add project root to path for imports
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from Link_Profiler.database.database import Database
from Link_Profiler.core.models import CrawlJob, CrawlStatus, LinkProfile, Domain
from Link_Profiler.config.config_loader import ConfigLoader # Import ConfigLoader

# Initialize and load config once using the absolute path
config_loader = ConfigLoader()
config_loader.load_config(config_dir=os.path.join(project_root, "Link_Profiler", "config"), env_var_prefix="LP_")

app = FastAPI(title="Link Profiler Monitor")
# Corrected template directory path
templates = Jinja2Templates(directory=os.path.join(project_root, "Link_Profiler", "monitoring", "templates"))

class MonitoringDashboard:
    def __init__(self):
        # Load Redis URL from config_loader, with fallback to environment variable then hardcoded default
        redis_url = config_loader.get("redis.url", os.getenv("REDIS_URL", "redis://localhost:6379/0"))
        self.redis_pool = redis.ConnectionPool.from_url(redis_url)
        self.redis = redis.Redis(connection_pool=self.redis_pool)
        
        # Load Database URL from config_loader, with fallback to environment variable then hardcoded default
        database_url = config_loader.get("database.url", os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/link_profiler_db"))
        self.db = Database(db_url=database_url)

        self.performance_window_seconds = config_loader.get("monitoring.performance_window", 3600)
        self.logger = logging.getLogger(__name__)

    async def get_queue_metrics(self) -> Dict:
        """Get comprehensive queue metrics"""
        try:
            job_queue_name = config_loader.get("queue.job_queue_name", "crawl_jobs")
            result_queue_name = config_loader.get("queue.result_queue_name", "crawl_results")
            
            job_queue_size = await self.redis.zcard(job_queue_name)
            result_queue_size = await self.redis.llen(result_queue_name)
            
            cutoff = (datetime.now() - timedelta(minutes=5)).timestamp()
            recent_heartbeats = await self.redis.zrangebyscore(
                "crawler_heartbeats_sorted", 
                cutoff, 
                "+inf", 
                withscores=True
            )
            
            satellites = []
            for heartbeat_data, timestamp in recent_heartbeats:
                try:
                    hb = json.loads(heartbeat_data)
                    hb['last_seen'] = datetime.fromtimestamp(timestamp)
                    satellites.append(hb)
                except json.JSONDecodeError:
                    self.logger.warning(f"Failed to decode heartbeat data: {heartbeat_data}")
                    continue
            
            return {
                "pending_jobs": job_queue_size,
                "results_pending": result_queue_size,
                "active_satellites": len(satellites),
                "satellites": satellites,
                "timestamp": datetime.now()
            }
            
        except Exception as e:
            self.logger.error(f"Error getting queue metrics: {e}", exc_info=True)
            return {"error": str(e), "timestamp": datetime.now()}
    
    async def get_job_history(self, limit: int = 50) -> List[Dict]:
        """Get recent job completion history from the database."""
        try:
            all_jobs = self.db.get_all_crawl_jobs()
            
            completed_jobs = sorted(
                [job for job in all_jobs if job.is_completed],
                key=lambda job: job.completed_date if job.completed_date else datetime.min,
                reverse=True
            )
            
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
            self.logger.error(f"Error getting job history: {e}", exc_info=True)
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
            
            # Use the new database method for performance trends
            trends_data = self.db.get_crawl_performance_trends(
                time_unit="hour", # Get hourly trends for recent performance
                num_units=int(self.performance_window_seconds / 3600) # Number of hours in window
            )
            
            total_jobs_in_window = sum(t['total_jobs'] for t in trends_data)
            successful_jobs_in_window = sum(t['successful_jobs'] for t in trends_data)
            
            jobs_per_hour = 0.0
            avg_job_duration = 0.0
            success_rate = 0.0

            if total_jobs_in_window > 0:
                jobs_per_hour = total_jobs_in_window / (self.performance_window_seconds / 3600)
                
                total_successful_duration = sum(t['avg_duration_seconds'] * t['successful_jobs'] for t in trends_data if t['successful_jobs'] > 0)
                total_successful_jobs_for_avg = sum(t['successful_jobs'] for t in trends_data)
                if total_successful_jobs_for_avg > 0:
                    avg_job_duration = total_successful_duration / total_successful_jobs_for_avg
                
                success_rate = (successful_jobs_in_window / total_jobs_in_window) * 100
            
            queue_metrics = await self.get_queue_metrics()
            active_satellites = queue_metrics.get("active_satellites", 0)
            pending_jobs = queue_metrics.get("pending_jobs", 0)

            current_load = 0.0
            if active_satellites > 0:
                current_load = min(1.0, pending_jobs / (active_satellites * 10))
            elif pending_jobs > 0:
                current_load = 1.0
            
            return {
                "memory_usage": memory_usage,
                "jobs_per_hour": round(jobs_per_hour, 2),
                "avg_job_duration": round(avg_job_duration, 2),
                "success_rate": round(success_rate, 1),
                "peak_satellites": active_satellites,
                "current_load": round(current_load, 2),
                "performance_window_seconds": self.performance_window_seconds,
                "trends_data": trends_data # Include detailed trends for potential future use
            }
            
        except Exception as e:
            self.logger.error(f"Error getting performance stats: {e}", exc_info=True)
            return {"error": str(e)}

    async def get_data_summaries(self) -> Dict:
        """
        Get summary statistics for various data types stored in the database.
        """
        try:
            # Total Link Profiles
            all_link_profiles = self.db.get_all_link_profiles()
            total_link_profiles = len(all_link_profiles)
            avg_link_profile_authority = sum(lp.authority_score for lp in all_link_profiles) / total_link_profiles if total_link_profiles > 0 else 0.0

            # Total Domains Analyzed & Valuable Expired Domains
            all_domains = self.db.get_all_domains()
            total_domains_analyzed = len(all_domains)
            valuable_expired_domains = len([d for d in all_domains if d.spam_score < 0.2 and d.authority_score > 30])

            # Competitive Keyword Analyses
            competitive_keyword_analyses = self.db.get_count_of_competitive_keyword_analyses()
            
            # Total Backlinks Stored
            total_backlinks_stored = len(self.db.get_all_backlinks())

            return {
                "total_link_profiles": total_link_profiles,
                "avg_link_profile_authority": round(avg_link_profile_authority, 2), # Round for display
                "total_domains_analyzed": total_domains_analyzed,
                "valuable_expired_domains": valuable_expired_domains,
                "competitive_keyword_analyses": competitive_keyword_analyses,
                "total_backlinks_stored": total_backlinks_stored
            }
        except Exception as e:
            self.logger.error(f"Error getting data summaries: {e}", exc_info=True)
            return {
                "total_link_profiles": "N/A",
                "avg_link_profile_authority": "N/A",
                "total_domains_analyzed": "N/A",
                "valuable_expired_domains": "N/A",
                "competitive_keyword_analyses": "N/A",
                "total_backlinks_stored": "N/A"
            }


# Global dashboard instance
dashboard = MonitoringDashboard()

@app.get("/", response_class=HTMLResponse)
async def monitoring_home(request: Request):
    """Main monitoring dashboard"""
    
    # Get all metrics
    queue_metrics = await dashboard.get_queue_metrics()
    job_history = await dashboard.get_job_history(config_loader.get("monitoring.max_job_history", 50))
    performance_stats = await dashboard.get_performance_stats()
    data_summaries = await dashboard.get_data_summaries()
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "queue_metrics": queue_metrics,
        "job_history": job_history,
        "performance_stats": performance_stats,
        "data_summaries": data_summaries,
        "refresh_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })

@app.get("/api/metrics")
async def get_metrics_api():
    """API endpoint for metrics (for external monitoring)"""
    queue_metrics = await dashboard.get_queue_metrics()
    performance_stats = await dashboard.get_performance_stats()
    data_summaries = await dashboard.get_data_summaries()
    
    return {
        **queue_metrics,
        **performance_stats,
        **data_summaries
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
    def __init__(self, redis_url: str = None):
        # Load Redis URL from config_loader, with fallback to environment variable then hardcoded default
        redis_url = redis_url or config_loader.get("redis.url", os.getenv("REDIS_URL", "redis://localhost:6379/0"))
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
        job_queue_name = config_loader.get("queue.job_queue_name", "crawl_jobs")
        result_queue_name = config_loader.get("queue.result_queue_name", "crawl_results")
        
        jobs = await self.redis.zcard(job_queue_name)
        results = await self.redis.llen(result_queue_name)
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
    import argparse
    
    parser = argparse.ArgumentParser(description="Link Profiler Monitoring CLI")
    parser.add_argument("--redis-url", default=None, help="Redis connection URL (overrides config/env)")
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
        uvicorn.run(app, host="0.0.0.0", port=config_loader.get("monitoring.monitor_port", 8001))
    elif args.command == "clear-jobs":
        await manager.clear_queue(config_loader.get("queue.job_queue_name", "crawl_jobs"))
    elif args.command == "clear-results":
        await manager.clear_queue(config_loader.get("queue.result_queue_name", "crawl_results"))
    elif args.command == "clear-dead-letters":
        await manager.clear_queue(config_loader.get("queue.dead_letter_queue_name", "dead_letter_queue"))
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
    import argparse
    asyncio.run(cli_main())
