from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional
from datetime import datetime
import logging

from Link_Profiler.database.database import Database
from Link_Profiler.core.models import CrawlStatus, CrawlJob, User
from Link_Profiler.api.schemas import CrawlJobResponse
from Link_Profiler.api.queue_endpoints import get_coordinator # This import is fine as it's not from main.py
from Link_Profiler.config.config_loader import ConfigLoader
from Link_Profiler.api.dependencies import get_current_user # Ensure this is imported for protected endpoints

# Initialize config_loader and db here
logger = logging.getLogger(__name__)
    
# These are now imported from main.py, so no need for dummy classes here.
# from Link_Profiler.main import db, config_loader 


public_jobs_router = APIRouter()

# --- Public Endpoints for Dashboard (no authentication required) ---

@public_jobs_router.get("/public/jobs", response_model=List[CrawlJobResponse])
async def public_jobs(
    status_filter: Optional[CrawlStatus] = Query(None, description="Filter jobs by status")
):
    """
    Public endpoint to retrieve a list of all crawl jobs, optionally filtered by status,
    without authentication. Returns the most recent 50 jobs.
    """
    logger.info(f"API: Received request for public jobs with status filter: {status_filter}")
    try:
        # Import db from main.py here to avoid circular dependency at module level
        from Link_Profiler.main import db 
        all_jobs = db.get_all_crawl_jobs()
        if status_filter:
            filtered_jobs = [job for job in all_jobs if job.status == status_filter]
        else:
            filtered_jobs = all_jobs
        
        # Sort by created_date descending and limit to 50
        sorted_jobs = sorted(filtered_jobs, key=lambda job: job.created_date if job.created_date else datetime.min, reverse=True)[:50]
        
        return [CrawlJobResponse.from_crawl_job(job) for job in sorted_jobs]
    except Exception as e:
        logger.error(f"Error retrieving public jobs: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve public crawl jobs.")

@public_jobs_router.get("/public/jobs/paused")
async def public_jobs_paused():
    """
    Public endpoint to check if job processing is paused without authentication.
    """
    logger.info("API: Received request for public job pause status.")
    try:
        coordinator = await get_coordinator()
        is_paused = await coordinator.is_paused()
        return {"is_paused": is_paused}
    except Exception as e:
        logger.error(f"Error checking public job pause status: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve public job pause status.")

# --- Protected Endpoints (require authentication) ---
# These were previously in this file but are now moved to monitoring_debug.py
# or are handled by other routers.
# The original request was to make /public/jobs and /public/jobs/paused.
# The /api/jobs/all and /api/jobs/is_paused (without /public/) are protected.
# I've moved the protected /api/jobs/all and /api/jobs/is_paused to monitoring_debug.py
# to consolidate monitoring-related protected endpoints there.
