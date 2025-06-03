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

# Add project root to path for imports
# Corrected project_root calculation to point to the repository root
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.sys.path.insert(0, project_root)

from Link_Profiler.database.database import Database
from Link_Profiler.core.models import CrawlJob, CrawlStatus, LinkProfile, Domain, serialize_model, CrawlConfig # Import CrawlConfig
from Link_Profiler.config.config_loader import ConfigLoader
from Link_Profiler.queue_system.job_coordinator import JobCoordinator # Import JobCoordinator
from Link_Profiler.api.queue_endpoints import QueueCrawlRequest, JobStatusResponse, get_coordinator # Import necessary models and functions

# Initialize and load config once using the absolute path
config_loader = ConfigLoader()
# The config_dir path is now correct relative to the new project_root
config_loader.load_config(config_dir=os.path.join(project_root, "Link_Profiler", "config"), env_var_prefix="LP_")

app = FastAPI(title="Link Profiler Monitor")
# Corrected template directory path relative to the new project_root
templates = Jinja2Templates(directory=os.path.join(project_root, "Link_Profiler", "monitoring", "templates"))

class MonitoringDashboard:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Initialize clients as None; they will be set up in __aenter__
        self.redis_pool: Optional[redis.ConnectionPool] = None
        self.redis: Optional[redis.Redis] = None
        self.db: Optional[Database] = None
        self._session: Optional[aiohttp.ClientSession] = None
        self.coordinator: Optional[JobCoordinator] = None # Add coordinator instance

        self.performance_window_seconds = config_loader.get("monitoring.performance_window", 3600)
        self.stale_timeout = config_loader.get("queue.stale_timeout", 60) # Get stale_timeout from config
        self.job_queue_name = config_loader.get("queue.job_queue_name", "crawl_jobs") # Added for is_paused endpoint
        self.dead_letter_queue_name = config_loader.get("queue.dead_letter_queue_name", "dead_letter_queue") # Added for is_paused endpoint

    async def __aenter__(self):
        """Initialise aiohttp session, Redis, and Database connections."""
        self.logger.info("Entering MonitoringDashboard context. Initialising connections.")
        
        # Initialize aiohttp session
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()

        # Initialize Redis connection
        redis_url = config_loader.get("redis.url", os.getenv("REDIS_URL", "redis://localhost:6379/0"))
        try:
            self.redis_pool = redis.ConnectionPool.from_url(redis_url)
            self.redis = redis.Redis(connection_pool=self.redis_pool)
            await self.redis.ping()
            self.logger.info("MonitoringDashboard connected to Redis successfully.")
        except Exception as e:
            self.logger.error(f"MonitoringDashboard failed to connect to Redis: {e}", exc_info=True)
            self.redis = None # Set to None if connection fails
            self.redis_pool = None

        # Initialize Database connection
        database_url = config_loader.get("database.url", os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/link_profiler_db"))
        try:
            self.db = Database(db_url=database_url)
            self.db.ping() # Use the ping method to test connection and create tables
            self.logger.info("MonitoringDashboard connected to PostgreSQL successfully.")
        except Psycopg2OperationalError as e:
            self.logger.error(f"MonitoringDashboard failed to connect to PostgreSQL: {e}", exc_info=True)
            self.db = None # Set to None if connection fails
        except Exception as e:
            self.logger.error(f"MonitoringDashboard encountered unexpected error with PostgreSQL: {e}", exc_info=True)
            self.db = None

        # Initialize JobCoordinator (without alert_service and connection_manager for dashboard context)
        # This coordinator instance is for dashboard's internal use, not the main API's coordinator.
        # It needs a DB and Redis client.
        if self.db and self.redis:
            self.coordinator = JobCoordinator(redis_url=redis_url, database=self.db)
            # No need to call __aenter__ on this coordinator as it's not running background tasks
            # It's just used for its methods like get_all_jobs_for_dashboard, pause_job_processing etc.
            self.logger.info("MonitoringDashboard: JobCoordinator instance created.")
        else:
            self.logger.warning("MonitoringDashboard: JobCoordinator could not be initialized due to missing DB or Redis connection.")

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close aiohttp session, Redis, and Database connections."""
        self.logger.info("Exiting MonitoringDashboard context. Closing connections.")
        
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
        
        if self.redis_pool:
            await self.redis_pool.disconnect()
            self.redis = None
            self.redis_pool = None
        
        # SQLAlchemy scoped_session is managed by its own lifecycle,
        # but explicit close might be needed if not using scoped_session correctly
        # For now, rely on the session's internal management or garbage collection.
        # If self.db has a close method, call it:
        # if self.db and hasattr(self.db, 'close'):
        #     self.db.close()

    async def get_queue_metrics(self) -> Dict:
        """Get comprehensive queue metrics"""
        if not self.redis:
            return {"error": "Redis not connected", "timestamp": datetime.now()}
        try:
            job_queue_name = config_loader.get("queue.job_queue_name", "crawl_jobs")
            result_queue_name = config_loader.get("queue.result_queue_name", "crawl_results")
            
            job_queue_size = await self.redis.zcard(job_queue_name)
            result_queue_size = await self.redis.llen(result_queue_name)
            
            # Get all crawler_ids and their last heartbeat timestamps from the sorted set
            # Only fetch those that are within the stale_timeout period
            cutoff = (datetime.now() - timedelta(seconds=self.stale_timeout)).timestamp()
            
            # Fetch members (crawler_ids) and their scores (timestamps)
            active_crawler_ids_with_timestamps = await self.redis.zrangebyscore(
                "crawler_heartbeats_sorted", 
                cutoff, 
                "+inf", 
                withscores=True
            )
            
            satellites = []
            for crawler_id_bytes, timestamp in active_crawler_ids_with_timestamps:
                crawler_id = crawler_id_bytes.decode('utf-8')
                
                # Fetch the detailed heartbeat data for this crawler_id
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
                        self.logger.warning(f"Failed to decode detailed heartbeat data for {crawler_id}: {detailed_heartbeat_json}")
                        continue
                else:
                    self.logger.warning(f"No detailed heartbeat data found for active crawler_id: {crawler_id}. It might have expired.")
            
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
        if not self.db:
            return []
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
        finally:
            # Ensure session is closed if not handled by scoped_session automatically
            if self.db and hasattr(self.db, 'Session'):
                self.db.Session.remove()

    async def get_performance_stats(self) -> Dict:
        """
        Get system performance statistics based on historical job data.
        Calculates jobs per hour, average job duration, and success rate.
        """
        if not self.redis or not self.db:
            return {"error": "Redis or DB not connected", "timestamp": datetime.now()}
        try:
            # Get Redis memory usage
            info = await self.redis.info("memory")
            memory_usage = info.get("used_memory_human", "Unknown")
            
            # Use the new database method for performance trends
            # Changed time_unit to "hour" to match dashboard intent
            trends_data = self.db.get_crawl_performance_trends(
                time_unit="hour", # Changed from "day" to "hour"
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
            return {"error": str(e), "timestamp": datetime.now()}
        finally:
            # Ensure session is closed if not handled by scoped_session automatically
            if self.db and hasattr(self.db, 'Session'):
                self.db.Session.remove()

    async def get_data_summaries(self) -> Dict:
        """
        Get summary statistics for various data types stored in the database.
        """
        if not self.db:
            return {
                "total_link_profiles": "N/A", "avg_link_profile_authority": "N/A",
                "total_domains_analyzed": "N/A", "valuable_expired_domains": "N/A",
                "competitive_keyword_analyses": "N/A", "total_backlinks_stored": "N/A",
                "error": "Database not connected"
            }
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
                "total_backlinks_stored": "N/A",
                "error": str(e)
            }
        finally:
            # Ensure session is closed if not handled by scoped_session automatically
            if self.db and hasattr(self.db, 'Session'):
                self.db.Session.remove()

    async def get_system_stats(self) -> Dict:
        """Get system resource statistics"""
        try:
            return {
                "cpu_percent": psutil.cpu_percent(interval=None), # Non-blocking
                "memory": {
                    "total": psutil.virtual_memory().total,
                    "available": psutil.virtual_memory().available,
                    "percent": psutil.virtual_memory().percent,
                    "used": psutil.virtual_memory().used
                },
                "disk": {
                    "total": psutil.disk_usage('/').total,
                    "used": psutil.disk_usage('/').used,
                    "free": psutil.disk_usage('/').free,
                    "percent": psutil.disk_usage('/').percent
                },
                "uptime": time.time() - psutil.boot_time()
            }
        except Exception as e:
            self.logger.error(f"Error getting system stats: {e}", exc_info=True)
            return {"status": "error", "message": str(e)}

    async def get_api_health(self):
        """Check API health by calling its /health endpoint"""
        if not self._session:
            return {"status": "error", "message": "Internal aiohttp session not ready."}

        api_port = config_loader.get('api.port', 8000)
        api_host = config_loader.get('api.host', '127.0.0.1') # Use configured API host
        api_base_url = f"http://{api_host}:{api_port}"
        try:
            async with self._session.get(f"{api_base_url}/health", timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    return {"status": "error", "code": resp.status, "message": f"API returned status {resp.status}"}
        except Exception as e:
            self.logger.error(f"Error checking API health: {e}", exc_info=True)
            return {"status": "error", "message": str(e)}

    async def get_redis_stats(self):
        """Get Redis statistics"""
        if not self.redis:
            return {"status": "disconnected", "message": "Redis client not initialized."}
        try:
            info = await self.redis.info()
            return {
                "connected_clients": info.get("connected_clients", 0),
                "used_memory": info.get("used_memory", 0),
                "used_memory_human": info.get("used_memory_human", "0B"),
                "keyspace_hits": info.get("keyspace_hits", 0),
                "keyspace_misses": info.get("keyspace_misses", 0),
                "status": "connected"
            }
        except Exception as e:
            self.logger.error(f"Error getting Redis stats: {e}", exc_info=True)
            return {"status": "error", "message": str(e)}

    async def get_database_stats(self):
        """Get database statistics using psycopg2"""
        if not self.db:
            return {"status": "disconnected", "message": "Database client not initialized."}
        try:
            # Use self.db.ping() to check connection
            self.db.ping()
            
            conn = psycopg2.connect(self.db.db_url)
            cur = conn.cursor()
            
            # Get table statistics
            # Changed 'tablename' to 'relname' as per PostgreSQL pg_stat_user_tables documentation
            cur.execute("""
                SELECT 
                    schemaname,
                    relname,
                    n_tup_ins as inserts,
                    n_tup_upd as updates,
                    n_tup_del as deletes
                FROM pg_stat_user_tables;
            """)
            
            tables = []
            for row in cur.fetchall():
                tables.append({
                    "schema": row[0],
                    "table": row[1],
                    "inserts": row[2],
                    "updates": row[3],
                    "deletes": row[4]
                })
            
            cur.close()
            conn.close()
            
            return {
                "status": "connected",
                "tables": tables
            }
        except Psycopg2OperationalError as e:
            self.logger.error(f"Error getting database stats (connection failed): {e}", exc_info=True)
            return {"status": "disconnected", "message": str(e)}
        except Exception as e:
            self.logger.error(f"Error getting database stats: {e}", exc_info=True)
            return {"status": "error", "message": str(e)}
        finally:
            # Ensure session is closed if not handled by scoped_session automatically
            if self.db and hasattr(self.db, 'Session'):
                self.db.Session.remove()

    async def get_all_dashboard_data(self) -> Dict[str, Any]:
        """Aggregates all data needed for the dashboard."""
        tasks = [
            self.get_queue_metrics(),
            self.get_job_history(config_loader.get("monitoring.max_job_history", 50)),
            self.get_performance_stats(),
            self.get_data_summaries(),
            self.get_system_stats(),
            self.get_api_health(),
            self.get_redis_stats(),
            self.get_database_stats(),
            self.coordinator.get_all_jobs_for_dashboard() if self.coordinator else asyncio.sleep(0) and [] # New: Fetch all jobs
        ]
        
        # Run all data fetching tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Assign results to a dictionary, handling potential errors
        data = {
            "queue_metrics": results[0] if not isinstance(results[0], Exception) else {"error": str(results[0])},
            "job_history": results[1] if not isinstance(results[1], Exception) else [],
            "performance_stats": results[2] if not isinstance(results[2], Exception) else {"error": str(results[2])},
            "data_summaries": results[3] if not isinstance(results[3], Exception) else {"error": str(results[3])},
            "system": results[4] if not isinstance(results[4], Exception) else {"error": str(results[4])},
            "api_health": results[5] if not isinstance(results[5], Exception) else {"error": str(results[5])},
            "redis": results[6] if not isinstance(results[6], Exception) else {"error": str(results[6])},
            "database": results[7] if not isinstance(results[7], Exception) else {"error": str(results[7])},
            "all_jobs": results[8] if not isinstance(results[8], Exception) else [], # New: All jobs data
            "timestamp": datetime.now().isoformat()
        }
        return data


# Global dashboard instance
dashboard = MonitoringDashboard()

@app.on_event("startup")
async def startup_event():
    await dashboard.__aenter__()

@app.on_event("shutdown")
async def shutdown_event():
    await dashboard.__aexit__(None, None, None)


@app.get("/", response_class=HTMLResponse)
async def monitoring_home(request: Request):
    """Main monitoring dashboard"""
    
    # Get all metrics for initial render
    all_data = await dashboard.get_all_dashboard_data()
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "queue_metrics": all_data["queue_metrics"],
        "job_history": all_data["job_history"],
        "performance_stats": all_data["performance_stats"],
        "data_summaries": all_data["data_summaries"],
        "system": all_data["system"], # Pass system stats
        "api_health": all_data["api_health"], # Pass API health
        "redis_stats": all_data["redis"], # Pass Redis stats
        "database_stats": all_data["database"], # Pass DB stats
        "all_jobs": all_data["all_jobs"], # New: Pass all jobs to template
        "refresh_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })

@app.get("/api/stats")
async def get_all_stats_api():
    """API endpoint for dashboard statistics (used by JavaScript for refresh)"""
    return await dashboard.get_all_dashboard_data()

@app.get("/api/metrics")
async def get_metrics_api():
    """API endpoint for metrics (for external monitoring)"""
    # This endpoint is for Prometheus metrics, not the dashboard's aggregated data.
    # It should ideally return Prometheus text format, but for now, it returns a subset of dashboard data.
    # If you have a separate Prometheus metrics endpoint in main.py, this one might be redundant.
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
        # Use the dashboard's internal health check logic
        api_health_data = await dashboard.get_api_health()
        redis_health_data = await dashboard.get_redis_stats()
        db_health_data = await dashboard.get_database_stats()

        overall_status = "healthy"
        dependencies = {}

        if api_health_data.get("status") == "error":
            overall_status = "unhealthy"
        dependencies["api"] = api_health_data

        if redis_health_data.get("status") != "connected":
            overall_status = "unhealthy"
        dependencies["redis"] = redis_health_data

        if db_health_data.get("status") != "connected":
            overall_status = "unhealthy"
        dependencies["postgresql"] = db_health_data

        status_code = 200 if overall_status == "healthy" else 503
        return Response(content=json.dumps({
            "status": overall_status,
            "timestamp": datetime.now().isoformat(),
            "dependencies": dependencies
        }, indent=2), media_type="application/json", status_code=status_code)

    except Exception as e:
        return {"status": "unhealthy", "error": str(e), "timestamp": datetime.now().isoformat()}

# New: API Endpoints for Job Management (for dashboard to interact with)
@app.post("/api/jobs/submit", status_code=status.HTTP_202_ACCEPTED)
async def submit_job_from_dashboard(request: QueueCrawlRequest):
    """Submit a new crawl job from the dashboard."""
    if not dashboard.coordinator:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Job coordinator not available.")
    
    try:
        # Convert config dict to CrawlConfig if provided
        crawl_config_obj = CrawlConfig.from_dict(request.config if request.config else {})
        
        job_id = str(uuid.uuid4())
        job_type = request.config.get("job_type", "backlink_discovery")
        
        job = CrawlJob(
            id=job_id,
            target_url=request.target_url,
            job_type=job_type,
            status=CrawlStatus.PENDING,
            priority=request.priority,
            created_date=datetime.now(),
            scheduled_at=request.scheduled_at,
            cron_schedule=request.cron_schedule,
            config=serialize_model(crawl_config_obj),
        )
        
        if job_type == "backlink_discovery":
            job.config["initial_seed_urls"] = request.initial_seed_urls
        elif job_type == "link_health_audit":
            job.config["source_urls_to_audit"] = request.initial_seed_urls # Re-use initial_seed_urls for this
        elif job_type == "technical_audit":
            job.config["urls_to_audit_tech"] = request.initial_seed_urls # Re-use initial_seed_urls for this
        elif job_type == "full_seo_audit":
            job.config["urls_to_audit_full_seo"] = request.initial_seed_urls # Re-use initial_seed_urls for this
        elif job_type == "domain_analysis":
            job.config["domain_names_to_analyze"] = request.initial_seed_urls # Re-use initial_seed_urls for this
        # Add other job type specific config assignments as needed

        await dashboard.coordinator.submit_crawl_job(job)
        return {"job_id": job_id, "status": "submitted", "message": "Job queued for processing"}
    except Exception as e:
        dashboard.logger.error(f"Error submitting job from dashboard: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to submit job: {e}")

@app.post("/api/jobs/pause_all", status_code=status.HTTP_200_OK)
async def pause_all_jobs_endpoint():
    """Pause all new job processing."""
    if not dashboard.coordinator:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Job coordinator not available.")
    success = await dashboard.coordinator.pause_job_processing()
    if not success:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to pause job processing.")
    return {"status": "success", "message": "All job processing paused."}

@app.post("/api/jobs/resume_all", status_code=status.HTTP_200_OK)
async def resume_all_jobs_endpoint():
    """Resume all job processing."""
    if not dashboard.coordinator:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Job coordinator not available.")
    success = await dashboard.coordinator.resume_job_processing()
    if not success:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to resume job processing.")
    return {"status": "success", "message": "All job processing resumed."}

@app.get("/api/jobs/is_paused", response_model=Dict[str, bool]) # New endpoint to check global pause status
async def is_jobs_paused_endpoint():
    """Check if global job processing is currently paused."""
    if not dashboard.redis:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Redis is not available.")
    try:
        is_paused = await dashboard.redis.exists("processing_paused")
        return {"is_paused": bool(is_paused)}
    except Exception as e:
        dashboard.logger.error(f"Error checking global pause status: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to check pause status: {e}")


@app.post("/api/jobs/{job_id}/cancel", status_code=status.HTTP_200_OK)
async def cancel_job_endpoint(job_id: str):
    """Cancel a specific job."""
    if not dashboard.coordinator:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Job coordinator not available.")
    success = await dashboard.coordinator.cancel_job(job_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found or cannot be cancelled.")
    return {"status": "success", "message": f"Job {job_id} cancelled."}

@app.post("/api/satellites/control/all/{command}", status_code=status.HTTP_200_OK)
async def control_all_satellites_endpoint(command: str):
    """Send a control command to all active satellites (e.g., 'PAUSE', 'RESUME', 'SHUTDOWN', 'RESTART')."""
    if not dashboard.coordinator:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Job coordinator not available.")
    
    valid_commands = ["PAUSE", "RESUME", "SHUTDOWN", "RESTART"]
    if command.upper() not in valid_commands:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid command. Must be one of: {', '.join(valid_commands)}")

    success = await dashboard.coordinator.send_global_control_command(command.upper())
    if not success:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to send global command '{command}'.")
    return {"status": "success", "message": f"Global command '{command}' sent to all satellites."}

@app.post("/api/satellites/control/{crawler_id}/{command}", status_code=status.HTTP_200_OK)
async def control_single_satellite_endpoint(crawler_id: str, command: str):
    """Send a control command to a specific satellite (e.g., 'PAUSE', 'RESUME', 'SHUTDOWN', 'RESTART')."""
    if not dashboard.coordinator:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Job coordinator not available.")
    
    valid_commands = ["PAUSE", "RESUME", "SHUTDOWN", "RESTART"]
    if command.upper() not in valid_commands:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid command. Must be one of: {', '.join(valid_commands)}")

    # Optional: Check if crawler_id is known/active before sending
    # For now, we send it regardless, and the satellite will ignore if it's not its ID.
    
    success = await dashboard.coordinator.send_control_command(crawler_id, command.upper())
    if not success:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to send command '{command}' to satellite '{crawler_id}'.")
    return {"status": "success", "message": f"Command '{command}' sent to satellite '{crawler_id}'."}


@app.get("/api/jobs/all", response_model=List[JobStatusResponse])
async def get_all_jobs_api(status_filter: Optional[str] = None):
    """Get all jobs for the dashboard."""
    if not dashboard.coordinator:
        logger.error("Dashboard API: Job coordinator not available when calling /api/jobs/all.")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Job coordinator not available.")
    try:
        # Explicitly manage session for this critical read operation
        # This ensures a fresh view of the database, especially if other processes are writing.
        session = dashboard.db._get_session()
        try:
            session.expire_all() # Ensure all objects in the session are refreshed from the database
            jobs = await dashboard.coordinator.get_all_jobs_for_dashboard(status_filter=status_filter)
            logger.debug(f"Dashboard API: Retrieved {len(jobs)} jobs from DB for /api/jobs/all.") # Debugging log
            return [JobStatusResponse.from_crawl_job(job) for job in jobs]
        finally:
            session.close() # Always close the session
    except Exception as e:
        logger.error(f"Dashboard API: Error retrieving all jobs for /api/jobs/all: {e}", exc_info=True)
        # Return a proper JSON error response for the frontend
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to retrieve all jobs: {e}")

@app.get("/api/jobs/{job_id}", response_model=JobStatusResponse)
async def get_single_job_api(job_id: str):
    """Get details for a single job."""
    if not dashboard.coordinator:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Job coordinator not available.")
    job = await dashboard.coordinator.get_job_status(job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
    return JobStatusResponse.from_crawl_job(job)


# CLI tool for queue management
class QueueManager:
    def __init__(self, redis_url: str = None):
        # Load Redis URL from config_loader, with fallback to environment variable then hardcoded default
        redis_url = redis_url or config_loader.get("redis.url", os.getenv("REDIS_URL", "redis://localhost:6379/0"))
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
        level=getattr(logging, args.log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    manager = QueueManager(redis_url=args.redis_url)
    
    if args.command == "dashboard":
        # Directly run uvicorn for the dashboard command
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
