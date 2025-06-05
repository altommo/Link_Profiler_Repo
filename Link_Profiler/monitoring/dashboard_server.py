"""
Production-Ready Monitoring Dashboard Server.
This module provides a FastAPI application to serve a monitoring dashboard
and expose Prometheus metrics.
"""

import logging
import os
from datetime import datetime
from typing import Dict, Any, List, Optional

from fastapi import FastAPI, Request, Response, Depends, HTTPException, status, Query # Import Query
import json # Import json
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# Import globally initialized instances from main.py (or dummy for standalone testing)
try:
    from Link_Profiler.main import (
        logger, db, redis_client, config_loader,
        domain_service_instance, backlink_service_instance, serp_service_instance,
        keyword_service_instance, ai_service_instance, clickhouse_loader_instance,
        auth_service_instance, get_coordinator
    )
    from Link_Profiler.api.dependencies import get_current_user
except ImportError:
    logger = logging.getLogger(__name__)
    logging.basicConfig(level=logging.INFO)
    # Dummy instances for testing or if main.py is not fully initialized
    class DummyDB:
        def ping(self): return True
        def get_all_crawl_jobs(self): return []
        def get_all_link_profiles(self): return []
        def get_all_domains(self): return []
        def get_count_of_competitive_keyword_analyses(self): return 0
        def get_all_backlinks(self): return []
        class Session:
            @staticmethod
            def remove(): pass
    db = DummyDB()
    class DummyRedisClient:
        async def ping(self): return True
        async def get(self, key): return None
        async def lrange(self, key, start, end): return []
        async def delete(self, key): return 0
        async def zadd(self, key, mapping): pass
        async def zcard(self, key): return 0
        async def llen(self, key): return 0
        async def zrangebyscore(self, key, min_score, max_score, withscores=False): return []
        def info(self): return {}
    redis_client = DummyRedisClient()
    class DummyConfigLoader:
        def get(self, key, default=None): return default
    config_loader = DummyConfigLoader()
    class DummyService:
        api_client = None
        enabled = False
        async def __aenter__(self): return self
        async def __aexit__(self, exc_type, exc_val, exc_tb): pass
    domain_service_instance = DummyService()
    backlink_service_instance = DummyService()
    serp_service_instance = DummyService()
    keyword_service_instance = DummyService()
    ai_service_instance = DummyService()
    clickhouse_loader_instance = None
    class DummyAuthService:
        def _check_secret_key(self): pass
    auth_service_instance = DummyAuthService()
    # Dummy get_coordinator for testing
    class DummyCoordinator:
        async def get_queue_stats(self):
            return {
                "pending_jobs": 0,
                "results_pending": 0,
                "active_crawlers": 0,
                "satellite_crawlers": {},
                "timestamp": datetime.now().isoformat()
            }
        async def control_satellite(self, crawler_id: str, command: str):
            return {"message": f"Dummy: Command {command} sent to {crawler_id}"}
        async def control_all_satellites(self, command: str):
            return {"message": f"Dummy: Command {command} sent to all satellites"}
        async def cancel_job(self, job_id: str):
            return True
        async def pause_job_processing(self):
            return True
        async def resume_job_processing(self):
            return True
    async def get_coordinator():
        return DummyCoordinator()


# Import Prometheus metrics and health check functions
from Link_Profiler.monitoring.prometheus_metrics import get_metrics_text
from Link_Profiler.api.monitoring_debug import health_check_internal, _get_aggregated_stats_for_api, _get_satellites_data_internal, verify_admin_access

# Import core models for type hinting in API responses
from Link_Profiler.core.models import CrawlStatus, User

# Determine project root for templates and static files
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
templates = Jinja2Templates(directory=os.path.join(project_root, "Link_Profiler", "templates"))

# Initialize FastAPI app
dashboard_app = FastAPI(
    title="Link Profiler Monitoring Dashboard",
    description="Real-time monitoring and health checks for the Link Profiler system.",
    version="0.1.0"
)

# Mount static files
dashboard_app.mount(
    "/static",
    StaticFiles(directory=os.path.join(project_root, "Link_Profiler", "templates", "static")),
    name="static",
)

@dashboard_app.get("/", response_class=HTMLResponse)
async def dashboard_home(request: Request):
    """
    Serves the main dashboard HTML page.
    """
    return templates.TemplateResponse("dashboard.html", {"request": request})

@dashboard_app.get("/health")
async def health_check_endpoint():
    """
    Performs a comprehensive health check of the API and its dependencies.
    """
    health_status = await health_check_internal()
    status_code = status.HTTP_200_OK if health_status["status"] == "healthy" else status.HTTP_503_SERVICE_UNAVAILABLE
    return Response(content=json.dumps(health_status, indent=2), media_type="application/json", status_code=status_code)

@dashboard_app.get("/metrics", response_class=Response)
async def prometheus_metrics_endpoint():
    """
    Exposes Prometheus metrics in the Prometheus text format.
    """
    return Response(content=get_metrics_text(), media_type="text/plain; version=0.0.4; charset=utf-8")

@dashboard_app.get("/api/stats")
async def get_api_stats_endpoint(current_user: User = Depends(get_current_user)):
    """
    Retrieves aggregated statistics for the Link Profiler system.
    Requires admin authentication.
    """
    verify_admin_access(current_user)
    logger.info(f"Dashboard: Received request for aggregated stats by admin: {current_user.username}.")
    return await _get_aggregated_stats_for_api()

@dashboard_app.get("/api/satellites")
async def get_satellites_endpoint(current_user: User = Depends(get_current_user)):
    """
    Retrieves detailed health information for all satellite crawlers.
    Requires admin authentication.
    """
    verify_admin_access(current_user)
    logger.info(f"Dashboard: Received request for detailed satellite health by admin: {current_user.username}.")
    return await _get_satellites_data_internal()

@dashboard_app.get("/api/jobs")
async def get_jobs_endpoint(
    status_filter: Optional[str] = Query(None, description="Filter jobs by status (e.g., 'PENDING', 'IN_PROGRESS', 'COMPLETED', 'FAILED', 'CANCELLED')."),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieves a list of crawl jobs, optionally filtered by status.
    Requires admin authentication.
    """
    verify_admin_access(current_user)
    logger.info(f"Dashboard: Received request for jobs by admin: {current_user.username} (status_filter: {status_filter}).")
    
    try:
        all_jobs = db.get_all_crawl_jobs()
        
        if status_filter:
            try:
                filter_status = CrawlStatus[status_filter.upper()]
                all_jobs = [job for job in all_jobs if job.status == filter_status]
            except KeyError:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid status_filter: {status_filter}. Must be one of {list(CrawlStatus.__members__.keys())}.")
        
        # Sort by created date, newest first
        sorted_jobs = sorted(all_jobs, key=lambda job: job.created_date, reverse=True)
        
        # Convert CrawlJob objects to their dictionary representation for JSON serialization
        return [job.to_dict() for job in sorted_jobs]
    except Exception as e:
        logger.error(f"Dashboard: Error retrieving jobs: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to retrieve jobs: {e}")
    finally:
        if db and hasattr(db, 'Session'):
            db.Session.remove()

@dashboard_app.post("/api/jobs/{job_id}/cancel")
async def cancel_job_endpoint(job_id: str, current_user: User = Depends(get_current_user)):
    """
    Cancels a specific crawl job.
    Requires admin authentication.
    """
    verify_admin_access(current_user)
    logger.info(f"Dashboard: Received request to cancel job {job_id} by admin: {current_user.username}.")
    try:
        coordinator = await get_coordinator()
        success = await coordinator.cancel_job(job_id)
        if success:
            return {"message": f"Job {job_id} cancelled successfully."}
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Job {job_id} not found or could not be cancelled.")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Dashboard: Error cancelling job {job_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to cancel job {job_id}: {e}")

@dashboard_app.post("/api/jobs/pause_all")
async def pause_all_jobs_endpoint(current_user: User = Depends(get_current_user)):
    """
    Pauses all new job processing.
    Requires admin authentication.
    """
    verify_admin_access(current_user)
    logger.info(f"Dashboard: Received request to pause all jobs by admin: {current_user.username}.")
    try:
        coordinator = await get_coordinator()
        await coordinator.pause_job_processing()
        return {"message": "All new job processing paused."}
    except Exception as e:
        logger.error(f"Dashboard: Error pausing all jobs: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to pause all jobs: {e}")

@dashboard_app.post("/api/jobs/resume_all")
async def resume_all_jobs_endpoint(current_user: User = Depends(get_current_user)):
    """
    Resumes all job processing.
    Requires admin authentication.
    """
    verify_admin_access(current_user)
    logger.info(f"Dashboard: Received request to resume all jobs by admin: {current_user.username}.")
    try:
        coordinator = await get_coordinator()
        await coordinator.resume_job_processing()
        return {"message": "All job processing resumed."}
    except Exception as e:
        logger.error(f"Dashboard: Error resuming all jobs: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to resume all jobs: {e}")

@dashboard_app.post("/api/satellites/control/{crawler_id}/{command}")
async def control_single_satellite_endpoint(crawler_id: str, command: str, current_user: User = Depends(get_current_user)):
    """
    Sends a control command to a specific satellite crawler.
    Commands: PAUSE, RESUME, SHUTDOWN, RESTART.
    Requires admin authentication.
    """
    verify_admin_access(current_user)
    logger.info(f"Dashboard: Received command '{command}' for satellite '{crawler_id}' by admin: {current_user.username}.")
    try:
        coordinator = await get_coordinator()
        response = await coordinator.send_control_command(crawler_id, command)
        return response
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Dashboard: Error controlling satellite {crawler_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to control satellite {crawler_id}: {e}")

@dashboard_app.post("/api/satellites/control/all/{command}")
async def control_all_satellites_endpoint(command: str, current_user: User = Depends(get_current_user)):
    """
    Sends a control command to all active satellite crawlers.
    Commands: PAUSE, RESUME, SHUTDOWN, RESTART.
    Requires admin authentication.
    """
    verify_admin_access(current_user)
    logger.info(f"Dashboard: Received command '{command}' for all satellites by admin: {current_user.username}.")
    try:
        coordinator = await get_coordinator()
        response = await coordinator.send_global_control_command(command)
        return response
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Dashboard: Error controlling all satellites: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to control all satellites: {e}")

# You can run this dashboard server independently for testing:
# uvicorn Link_Profiler.monitoring.dashboard_server:dashboard_app --host 0.0.0.0 --port 8001 --reload
