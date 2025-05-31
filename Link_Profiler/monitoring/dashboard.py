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
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from Link_Profiler.database.database import Database # Import Database
from Link_Profiler.core.models import CrawlJob, CrawlStatus, LinkProfile, Domain # Import CrawlJob model and CrawlStatus, and new models
from Link_Profiler.config.config_loader import config_loader # Import config_loader

app = FastAPI(title="Link Profiler Monitor")
templates = Jinja2Templates(directory=os.path.join(project_root, "Link_Profiler", "templates")) # Corrected and robust path to templates

class MonitoringDashboard:
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_pool = redis.ConnectionPool.from_url(redis_url)
        self.redis = redis.Redis(connection_pool=self.redis_pool)
        self.db = Database() # Initialize database connection for job history
        self.performance_window_seconds = config_loader.get("monitoring.performance_window", 3600) # Default to 1 hour
        self.logger = logging.getLogger(__name__)

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
                "current_load": round(current_load, 2),
                "performance_window_seconds": self.performance_window_seconds # Pass window size for display
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
            # Assuming 'is_valuable' might be a property or derived from spam_score/authority_score
            valuable_expired_domains = len([d for d in all_domains if d.spam_score < 0.2 and d.authority_score > 30]) # Example heuristic

            # Competitive Keyword Analyses
            competitive_keyword_analyses = self.db.get_count_of_competitive_keyword_analyses()
            
            # Total Backlinks Stored
            total_backlinks_stored = len(self.db.get_all_backlinks())

            return {
                "total_link_profiles": total_link_profiles,
                "avg_link_profile_authority": avg_link_profile_authority,
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
    data_summaries = await dashboard.get_data_summaries() # New: Fetch data summaries
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "queue_metrics": queue_metrics,
        "job_history": job_history,
        "performance_stats": performance_stats,
        "data_summaries": data_summaries, # Pass data summaries to template
        "refresh_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })

@app.get("/api/metrics")
async def get_metrics_api():
    """API endpoint for metrics (for external monitoring)"""
    queue_metrics = await dashboard.get_queue_metrics()
    performance_stats = await dashboard.get_performance_stats()
    data_summaries = await dashboard.get_data_summaries() # New: Fetch data summaries
    
    return {
        **queue_metrics,
        **performance_stats,
        **data_summaries # Include data summaries in API metrics
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
