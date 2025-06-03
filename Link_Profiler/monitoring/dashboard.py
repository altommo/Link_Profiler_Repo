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
    sys.sys.path.insert(0, project_root)

from Link_Profiler.database.database import Database
from Link_Profiler.core.models import CrawlJob, CrawlStatus, LinkProfile, Domain, serialize_model, CrawlConfig # Import CrawlConfig
from Link_Profiler.config.config_loader import ConfigLoader
from Link_Profiler.queue_system.job_coordinator import JobCoordinator # Import JobCoordinator
from Link_Profiler.api.queue_endpoints import get_coordinator, QueueCrawlRequest # Corrected: Import QueueCrawlRequest from queue_endpoints
from Link_Profiler.api.schemas import JobStatusResponse # Corrected: Import JobStatusResponse from schemas

# Initialize and load config once using the absolute path
# The config_dir path is now correct relative to the new project_root
config_loader = ConfigLoader()
config_loader.load_config(config_dir=os.path.join(project_root, "Link_Profiler", "config"), env_var_prefix="LP_")

app = FastAPI(title="Link Profiler Monitor")
# Corrected template directory path relative to the new project_root
templates = Jinja2Templates(directory=os.path.join(project_root, "Link_Profiler", "monitoring", "templates"))

# Initialize logger for this module
logger = logging.getLogger(__name__)

class MonitoringDashboard:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Initialize clients as None; they will be set up in __aenter__
        self.redis_pool: Optional[redis.ConnectionPool] = None
        self.redis: Optional[redis.Redis] = None # This is the attribute holding the Redis client
        self.db: Optional[Database] = None
        self._session: Optional[aiohttp.ClientSession] = None
        self.coordinator: Optional[JobCoordinator] = None # Add coordinator instance
        self.api_access_token: Optional[str] = None # New: Store API access token
        self.main_api_internal_url: str = "" # New: Store main API's internal URL for backend-to-backend calls
        self._token_refresh_task: Optional[asyncio.Task] = None # New: Task for token renewal

        self.performance_window_seconds = config_loader.get("monitoring.performance_window", 3600)
        self.stale_timeout = config_loader.get("queue.stale_timeout", 60) # Get stale_timeout from config
        self.job_queue_name = config_loader.get("queue.job_queue_name", "crawl_jobs") # Added for is_paused endpoint
        self.dead_letter_queue_name = config_loader.get("queue.dead_letter_queue_name", "dead_letter_queue") # Added for is_paused endpoint
        self.access_token_expire_minutes = config_loader.get("auth.access_token_expire_minutes", 30) # New: Get token expiry
        
        # New: Monitor user credentials
        self.monitor_username = config_loader.get("monitoring.monitor_auth.username")
        self.monitor_password = config_loader.get("monitoring.monitor_auth.password")

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
            # Corrected: Pass self.redis (the client instance) and config_loader
            self.coordinator = JobCoordinator(redis_client=self.redis, database=self.db, config_loader=config_loader)
            # No need to call __aenter__ on this coordinator as it's not running background tasks
            # It's just used for its methods like get_all_jobs_for_dashboard, pause_job_processing etc.
            self.logger.info("MonitoringDashboard: JobCoordinator instance created.")
        else:
            self.logger.warning("MonitoringDashboard: JobCoordinator could not be initialized due to missing DB or Redis connection.")

        # New: Obtain initial API access token for the dashboard itself
        # This is the internal URL for Docker Compose services or localhost for Linux services
        self.main_api_internal_url = config_loader.get('api.internal_url', 'http://localhost:8000') # Use config_loader for internal URL
        self.logger.info(f"MonitoringDashboard: Main API internal URL set to {self.main_api_internal_url}")
        
        await self._refresh_access_token() # Get initial token

        # Start token renewal task if token was successfully obtained
        if self.api_access_token:
            self._token_refresh_task = asyncio.create_task(self._token_renewal_loop())
            self.logger.info("MonitoringDashboard: Started token renewal background task.")
        else:
            self.logger.warning("MonitoringDashboard: No initial token obtained, token renewal task not started.")

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close aiohttp session, Redis, and Database connections."""
        self.logger.info("Exiting MonitoringDashboard context. Closing connections.")
        
        # Cancel token refresh task
        if self._token_refresh_task:
            self._token_refresh_task.cancel()
            try:
                await self._token_refresh_task
            except asyncio.CancelledError:
                self.logger.info("MonitoringDashboard: Token renewal task cancelled.")
            except Exception as e:
                self.logger.error(f"MonitoringDashboard: Error cancelling token renewal task: {e}")

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

    async def _refresh_access_token(self):
        """Authenticates with the main API and obtains a new access token."""
        if not self.monitor_username or not self.monitor_password:
            self.logger.error("MonitoringDashboard: Monitor authentication credentials not found in config. Cannot refresh token.")
            self.api_access_token = None
            return

        try:
            token_url = f"{self.main_api_internal_url}/auth/token"
            token_data = {
                "username": self.monitor_username,
                "password": self.monitor_password
            }
            self.logger.debug(f"MonitoringDashboard: Attempting to get token from {token_url} with username {self.monitor_username}.")
            
            # Use aiohttp.FormData for application/x-www-form-urlencoded
            form_data = aiohttp.FormData()
            form_data.add_field('username', self.monitor_username)
            form_data.add_field('password', self.monitor_password)

            async with self._session.post(token_url, data=form_data, timeout=aiohttp.ClientTimeout(total=10)) as response:
                self.logger.debug(f"MonitoringDashboard: Token refresh response status: {response.status}")
                
                response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)
                
                token_response = await response.json()
                self.logger.debug(f"MonitoringDashboard: Token refresh response body: {token_response}")
                
                self.api_access_token = token_response.get("access_token")
                self.logger.info("MonitoringDashboard: Successfully refreshed API access token.")
        except aiohttp.ClientResponseError as e:
            self.logger.error(f"MonitoringDashboard: Failed to refresh API access token from {token_url} (Status: {e.status}, Detail: {e.message or await response.text()}). Check monitor_user credentials or main API status.", exc_info=True)
            self.api_access_token = None
        except aiohttp.ClientError as e:
            self.logger.error(f"MonitoringDashboard: Network error connecting to main API at {token_url} during token refresh: {e}. Is main API running?", exc_info=True)
            self.api_access_token = None
        except Exception as e:
            self.logger.error(f"MonitoringDashboard: Unexpected error during token refresh: {e}", exc_info=True)
            self.api_access_token = None

    async def _token_renewal_loop(self):
        """Periodically refreshes the API access token."""
        # Renew token a few minutes before it expires
        refresh_interval_seconds = (self.access_token_expire_minutes - 5) * 60 
        if refresh_interval_seconds <= 0:
            refresh_interval_seconds = 1 * 60 # Ensure at least 1 minute if expiry is too short

        self.logger.info(f"MonitoringDashboard: Token will be refreshed every {refresh_interval_seconds} seconds.")
        while True:
            await asyncio.sleep(refresh_interval_seconds)
            self.logger.info("MonitoringDashboard: Attempting to refresh API access token...")
            await self._refresh_access_token()
            if not self.api_access_token:
                self.logger.error("MonitoringDashboard: Token refresh failed. Retrying in 60 seconds.")
                await asyncio.sleep(60) # Short retry if refresh fails

    async def _call_main_api(self, endpoint: str, method: str = 'GET', json_data: Optional[Dict] = None) -> Any:
        """Helper to call the main FastAPI API with authentication."""
        if not self.api_access_token:
            self.logger.error(f"Attempted to call main API endpoint {endpoint} without an access token.")
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Dashboard not authenticated with main API.")

        headers = {
            "Authorization": f"Bearer {self.api_access_token}",
            "Content-Type": "application/json"
        }
        url = f"{self.main_api_internal_url}{endpoint}" # Use internal URL for backend-to-backend calls
        
        try:
            async with self._session.request(method, url, headers=headers, json=json_data, timeout=aiohttp.ClientTimeout(total=10)) as response:
                response.raise_for_status()
                return await response.json()
        except aiohttp.ClientResponseError as e:
            self.logger.error(f"Main API call failed for {url} (Status: {e.status}): {e.message}", exc_info=True)
            raise HTTPException(status_code=e.status, detail=f"Main API error: {e.message}")
        except aiohttp.ClientError as e:
            self.logger.error(f"Network error calling main API {url}: {e}", exc_info=True)
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"Could not connect to main API: {e}")
        except Exception as e:
            self.logger.error(f"Unexpected error calling main API {url}: {e}", exc_info=True)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Unexpected error: {e}")

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
        # This now calls the main API's health endpoint using the obtained token
        try:
            health_data = await self._call_main_api("/health")
            return health_data
        except HTTPException as e:
            return {"status": "error", "message": e.detail, "code": e.status_code}
        except Exception as e:
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

    async def _empty_list_awaitable(self) -> List[Any]:
        """Helper async method to return an empty list."""
        return []

    async def get_all_dashboard_data(self) -> Dict[str, Any]:
        """Aggregates all data needed for the dashboard."""
        tasks = [
            self.get_queue_metrics(),
            self.get_job_history(config_loader.get("monitoring.max_job_history", 50)),
            self.get_performance_stats(),
            self.get_data_summaries(),
            self.get_system_stats(),
            self.get_api_health(), # This now calls the main API
            self.get_redis_stats(),
            self.get_database_stats(),
            # Corrected: Ensure this always returns an awaitable
            self._call_main_api("/api/jobs/all") if self.api_access_token else self._empty_list_awaitable()
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
    
    # Construct the external API base URL for the frontend JavaScript
    # Prioritize api.external_url from config, then fallback to request.url.scheme + api.host:api.port
    main_api_external_base_url = config_loader.get('api.external_url')
    
    logger.debug(f"Configured api.external_url for frontend: {main_api_external_base_url}")

    if not main_api_external_base_url:
        logger.critical("CRITICAL ERROR: 'api.external_url' is not configured in config.yaml or via environment variables. "
                        "The dashboard frontend will not be able to connect to the main API. "
                        "Please set api.external_url to the public HTTPS URL of your main API (e.g., 'https://monitor.yspanel.com:8000').")
        # Fallback to a potentially incorrect URL, but log a critical error
        main_api_external_base_url = f"{request.url.scheme}://{request.url.hostname}:{config_loader.get('api.port', 8000)}"
        
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
        "refresh_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "access_token": dashboard.api_access_token, # Pass the dynamically obtained token
        "api_base_url": main_api_external_base_url, # Pass the external API base URL for frontend
        "monitor_username": dashboard.monitor_username, # Pass monitor username to frontend
        "monitor_password": dashboard.monitor_password, # Pass monitor password to frontend (for client-side auth)
        "access_token_expire_minutes": dashboard.access_token_expire_minutes # Pass token expiry to frontend
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

@app.post("/api/jobs/submit", status_code=status.HTTP_202_ACCEPTED)
async def submit_job_from_dashboard(request: QueueCrawlRequest):
    """Submit a new crawl job from the dashboard."""
    # This endpoint now proxies the request to the main API
    try:
        response_data = await dashboard._call_main_api("/api/queue/submit_crawl", method="POST", json_data=request.dict()) # Corrected endpoint
        return response_data
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error submitting job from dashboard (proxying to main API): {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to submit job via main API: {e}")

@app.post("/api/jobs/pause_all", status_code=status.HTTP_200_OK)
async def pause_all_jobs_endpoint():
    """Pause all new job processing."""
    # This endpoint now proxies the request to the main API
    try:
        response_data = await dashboard._call_main_api("/api/jobs/pause_all", method="POST")
        return response_data
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error pausing all jobs from dashboard (proxying to main API): {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to pause all jobs via main API: {e}")

@app.post("/api/jobs/resume_all", status_code=status.HTTP_200_OK)
async def resume_all_jobs_endpoint():
    """Resume all job processing."""
    # This endpoint now proxies the request to the main API
    try:
        response_data = await dashboard._call_main_api("/api/jobs/resume_all", method="POST")
        return response_data
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error resuming all jobs from dashboard (proxying to main API): {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to resume all jobs via main API: {e}")

@app.get("/api/jobs/is_paused", response_model=Dict[str, bool]) # New endpoint to check global pause status
async def is_jobs_paused_endpoint():
    """Check if global job processing is currently paused."""
    # This endpoint now proxies the request to the main API
    try:
        response_data = await dashboard._call_main_api("/api/jobs/is_paused", method="GET")
        return response_data
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error checking global pause status from dashboard (proxying to main API): {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to check pause status via main API: {e}")


@app.post("/api/jobs/{job_id}/cancel", status_code=status.HTTP_200_OK)
async def cancel_job_endpoint(job_id: str):
    """Cancel a specific job."""
    # This endpoint now proxies the request to the main API
    try:
        response_data = await dashboard._call_main_api(f"/api/jobs/{job_id}/cancel", method="POST")
        return response_data
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error cancelling job {job_id} from dashboard (proxying to main API): {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to cancel job via main API: {e}")

@app.post("/api/satellites/control/all/{command}", status_code=status.HTTP_200_OK)
async def control_all_satellites_endpoint(command: str):
    """Send a control command to all active satellites (e.g., 'PAUSE', 'RESUME', 'SHUTDOWN', 'RESTART')."""
    # This endpoint now proxies the request to the main API
    try:
        response_data = await dashboard._call_main_api(f"/api/satellites/control/all/{command}", method="POST")
        return response_data
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error sending global control command '{command}' from dashboard (proxying to main API): {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to send global command via main API: {e}")

@app.post("/api/satellites/control/{crawler_id}/{command}", status_code=status.HTTP_200_OK)
async def control_single_satellite_endpoint(crawler_id: str, command: str):
    """Send a control command to a specific satellite (e.g., 'PAUSE', 'RESUME', 'SHUTDOWN', 'RESTART')."""
    # This endpoint now proxies the request to the main API
    try:
        response_data = await dashboard._call_main_api(f"/api/satellites/control/{crawler_id}/{command}", method="POST")
        return response_data
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error sending control command '{command}' to satellite '{crawler_id}' from dashboard (proxying to main API): {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to send command to satellite via main API: {e}")


# CLI tool for queue management
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
