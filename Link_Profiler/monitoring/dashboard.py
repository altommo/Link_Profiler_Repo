"""
Monitoring Dashboard for Distributed Link Profiler
Simple web interface to monitor queue status and satellites
"""
import asyncio
import json
import uuid # Import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import redis.asyncio as redis
from fastapi import FastAPI, Request, Response, HTTPException, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import uvicorn
import logging
import sys
import os
import psutil
import psycopg2
from psycopg2 import OperationalError as Psycopg2OperationalError
import aiohttp
import time

# Add project root to path
# Corrected project_root calculation to point to the repository root
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from Link_Profiler.database.database import Database
from Link_Profiler.core.models import CrawlJob, CrawlStatus, LinkProfile, Domain, serialize_model, CrawlConfig # Import CrawlConfig
from Link_Profiler.config.config_loader import ConfigLoader
from Link_Profiler.queue_system.job_coordinator import JobCoordinator # Import JobCoordinator
from Link_Profiler.api.schemas import JobStatusResponse # Corrected: Import JobStatusResponse from schemas
from Link_Profiler.api.schemas import StartCrawlRequest # Corrected: Import StartCrawlRequest from schemas

# Initialize and load config once using the absolute path
# The config_dir path is now correct relative to the new project_root
config_loader = ConfigLoader()
config_loader.load_config(config_dir=os.path.join(project_root, "Link_Profiler", "config"), env_var_prefix="LP_")

app = FastAPI(title="Link Profiler Monitor")
# Unified template directory path relative to the project_root
templates = Jinja2Templates(directory=os.path.join(project_root, "admin-management-console"))

# Initialize logger for this module
logger = logging.getLogger(__name__)

# Removed MonitoringDashboard class and its methods.
# The dashboard is now served by the main API, and its data fetching logic
# is integrated into Link_Profiler/api/monitoring_debug.py.

# Global dashboard instance is no longer needed here.
# dashboard = MonitoringDashboard()

# The lifespan context manager is now handled in main.py for the main FastAPI app.
# @app.on_event("startup")
# async def startup_event():
#     await dashboard.__aenter__()

# @app.on_event("shutdown")
# async def shutdown_event():
#     await dashboard.__aexit__(None, None, None)


@app.get("/", response_class=HTMLResponse)
async def monitoring_home(request: Request):
    """Main monitoring dashboard"""
    
    # This endpoint is now served by the main API (Link_Profiler/main.py)
    # and will render the dashboard.html template.
    # The data fetching for the dashboard is done via JavaScript calls to /api/stats etc.
    return templates.TemplateResponse("dashboard.html", {"request": request})

# Removed all /api/* endpoints from this file.
# They are now handled by routers in Link_Profiler/api/
# (e.g., api/queue.py, api/monitoring_debug.py, api/public_jobs.py)

# The cli_main function is no longer needed as a separate async function.
# Its logic is moved directly into the __main__ block.

if __name__ == "__main__":
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
        level=getattr(logging, args.log_level.upper()), # Corrected: Use logging.Logger
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # The QueueManager is now part of the CLI only, not the FastAPI app in this file.
    class QueueManager:
        def __init__(self, redis_url: str = None):
            # Load Redis URL from config_loader, with fallback to environment variable then hardcoded default
            redis_url = config_loader.get("redis.url", os.getenv("REDIS_URL", "redis://localhost:6379/0"))
            self.redis_pool = redis.ConnectionPool.from_url(redis_url)
            self.redis = redis.Redis(connection_pool=self.redis_pool)
            self.stale_timeout = config_loader.get("queue.stale_timeout", 60) # Get stale_timeout from config
        
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
            cutoff = (datetime.now() - timedelta(seconds=self.stale_timeout)).timestamp()
            recent_crawler_ids_with_timestamps = await self.redis.zrangebyscore(
                "crawler_heartbeats_sorted", 
                cutoff, 
                "+inf", 
                withscores=True
            )
            
            satellites = []
            for crawler_id_bytes, timestamp in recent_crawler_ids_with_timestamps:
                crawler_id = crawler_id_bytes.decode('utf-8')
                detailed_heartbeat_json = await self.redis.get(f"crawler_details:{crawler_id}")
                
                if detailed_heartbeat_json:
                    try:
                        hb = json.loads(detailed_heartbeat_json)
                        # Add status based on stale_timeout
                        time_diff = datetime.now() - datetime.fromisoformat(hb.get("timestamp"))
                        hb['status'] = "healthy" if time_diff.total_seconds() < self.stale_timeout else "stale"
                        hb['last_seen'] = datetime.fromisoformat(hb.get("timestamp")) # Convert to datetime object
                        satellites.append(hb)
                    except json.JSONDecodeError:
                        logging.warning(f"Failed to decode detailed heartbeat data for {crawler_id} in list_satellites: {detailed_heartbeat_json}")
                        continue
                else:
                    logging.warning(f"No detailed heartbeat data found for active crawler_id: {crawler_id} in list_satellites.")

            print(f"Known Active Satellites ({len(satellites)}):")
            if satellites:
                for sat in sorted(satellites, key=lambda x: x.get('crawler_id', '')):
                    last_seen_dt = datetime.fromisoformat(sat.get('timestamp'))
                    time_diff = datetime.now() - last_seen_dt
                    status = "healthy" if time_diff.total_seconds() < self.stale_timeout else "stale"
                    print(f"  - ID: {sat.get('crawler_id')}, Region: {sat.get('region')}, Status: {status}, Running Jobs: {sat.get('running_jobs')}, Last Seen: {last_seen_dt.strftime('%Y-%m-%d %H:%M:%S')}")
            else:
                print("  No active satellites detected in the last 5 minutes.")

    manager = QueueManager(redis_url=args.redis_url)
    
    if args.command == "dashboard":
        # Directly run uvicorn for the dashboard command
        # This will run the FastAPI app defined in this file.
        uvicorn.run(app, host="0.0.0.0", port=config_loader.get("monitoring.monitor_port", 8001))
    else:
        # For other async CLI commands, use asyncio.run() to manage the event loop
        async def run_cli_command():
            if args.command == "clear-jobs":
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
                parser.print_help() # This will print help and exit, no async needed

        asyncio.run(run_cli_command())
