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
from fastapi.responses import HTMLResponse, RedirectResponse # Import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# --- Global Dependency Imports and Dummy Implementations ---
# This block attempts to import core components from main.py.
# If main.py or its dependencies are not fully set up (e.g., during standalone testing),
# dummy implementations are provided to prevent crashes.
try:
    from Link_Profiler.main import (
        logger, db, redis_client, config_loader,
        domain_service_instance, backlink_service_instance, serp_service_instance,
        keyword_service_instance, ai_service_instance, clickhouse_loader_instance,
        auth_service_instance, get_coordinator
    )
except ImportError:
    # Fallback logger for standalone operation
    logger = logging.getLogger(__name__)
    logging.basicConfig(level=logging.INFO)
    logger.warning("Could not import core components from Link_Profiler.main. Using dummy implementations for dashboard_server.")

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

# --- Ensure get_current_user is always defined ---
# This block specifically handles the import of get_current_user.
# It ensures that even if the main application context is not fully available,
# a dummy get_current_user is provided to allow the dashboard to run.
try:
    from Link_Profiler.api.dependencies import get_current_user
except ImportError:
    logger.warning("Could not import get_current_user from Link_Profiler.api.dependencies. Using dummy implementation.")
    # Create dummy get_current_user function for standalone testing
    def get_current_user():
        """Dummy get_current_user for standalone testing"""
        from Link_Profiler.core.models import User
        # Re-import datetime here to ensure it's available in the dummy function's scope
        from datetime import datetime
        return User(
            user_id="dummy-admin",
            username="admin",
            email="admin@test.com",
            is_admin=True,
            created_date=datetime.now(),
            updated_date=datetime.now(),
            last_login=datetime.now()
        )

# Import Prometheus metrics and health check functions
from Link_Profiler.monitoring.prometheus_metrics import get_metrics_text
from Link_Profiler.api.monitoring_debug import health_check_internal, _get_aggregated_stats_for_api, _get_satellites_data_internal, verify_admin_access

# Import core models for type hinting in API responses
from Link_Profiler.core.models import CrawlStatus, User

# Determine project root for templates and static files
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
templates = Jinja2Templates(directory=os.path.join(project_root, "admin-management-console"))

# Initialize FastAPI app
dashboard_app = FastAPI(
    title="Link Profiler Monitoring Dashboard",
    description="Real-time monitoring and health checks for the Link Profiler system.",
    version="0.1.0"
)

# Mount static files
dashboard_app.mount(
    "/static",
    StaticFiles(directory=os.path.join(project_root, "admin-management-console", "static")),
    name="static",
)

@dashboard_app.get("/", response_class=HTMLResponse)
async def dashboard_home(request: Request):
    """
    Serves the main dashboard HTML page, now deprecated.
    """
    # Redirect to the new Mission Control Dashboard
    return RedirectResponse(url="/mission-control", status_code=status.HTTP_302_FOUND)

@dashboard_app.get("/health")
async def health_check_endpoint():
    """
    Performs a comprehensive health check of the API and its dependencies.
    This endpoint remains active for external monitoring tools.
    """
    health_status = await health_check_internal()
    status_code = status.HTTP_200_OK if health_status["status"] == "healthy" else status.HTTP_503_SERVICE_UNAVAILABLE
    return Response(content=json.dumps(health_status, indent=2), media_type="application/json", status_code=status_code)

@dashboard_app.get("/metrics", response_class=Response)
async def prometheus_metrics_endpoint():
    """
    Exposes Prometheus metrics in the Prometheus text format.
    This endpoint remains active for external monitoring tools.
    """
    return Response(content=get_metrics_text(), media_type="text/plain; version=0.0.4; charset=utf-8")

# The following API endpoints are being removed from dashboard_server.py
# and will be moved to Link_Profiler/main.py or consumed directly from queue_endpoints.py
# by the new Mission Control Dashboard.

# @dashboard_app.get("/api/stats")
# async def get_api_stats_endpoint(current_user: User = Depends(get_current_user)):
#     ...

# @dashboard_app.get("/api/satellites")
# async def get_satellites_endpoint(current_user: User = Depends(get_current_user)):
#     ...

# @dashboard_app.get("/api/jobs")
# async def get_jobs_endpoint(
#     status_filter: Optional[str] = Query(None, description="Filter jobs by status..."),
#     current_user: User = Depends(get_current_user)
# ):
#     ...

# @dashboard_app.post("/api/jobs/{job_id}/cancel")
# async def cancel_job_endpoint(job_id: str, current_user: User = Depends(get_current_user)):
#     ...

# @dashboard_app.post("/api/jobs/pause_all")
# async def pause_all_jobs_endpoint(current_user: User = Depends(get_current_user)):
#     ...

# @dashboard_app.post("/api/jobs/resume_all")
# async def resume_all_jobs_endpoint(current_user: User = Depends(get_current_user)):
#     ...

# @dashboard_app.post("/api/satellites/control/{crawler_id}/{command}")
# async def control_single_satellite_endpoint(crawler_id: str, command: str, current_user: User = Depends(get_current_user)):
#     ...

# @dashboard_app.post("/api/satellites/control/all/{command}")
# async def control_all_satellites_endpoint(command: str, current_user: User = Depends(get_current_user)):
#     ...

# You can run this dashboard server independently for testing:
# uvicorn Link_Profiler.monitoring.dashboard_server:dashboard_app --host 0.0.0.0 --port 8001 --reload
