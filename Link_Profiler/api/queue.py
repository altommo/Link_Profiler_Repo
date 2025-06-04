import logging
from datetime import datetime
from typing import Annotated, Dict, Any, Optional, List

from fastapi import APIRouter, Depends, HTTPException, status, Query

# Import global instances and utility functions
# Removed direct import of submit_crawl_to_queue and get_coordinator from main.py
# from Link_Profiler.main import logger # Removed direct import of logger from main.py
logger = logging.getLogger(__name__) # Get logger directly

from Link_Profiler.services.job_submission_service import get_coordinator, submit_crawl_to_queue # New: Import from job_submission_service


# Import shared Pydantic models and dependencies
from Link_Profiler.api.schemas import (
    JobStatusResponse, QueueStatsResponse, CrawlerHealthResponse,
    StartCrawlRequest
)

from Link_Profiler.api.dependencies import get_current_user

# Import core models
from Link_Profiler.core.models import User, CrawlStatus


queue_router = APIRouter(prefix="/api/queue", tags=["Queue Management"])

@queue_router.post("/submit_crawl", response_model=Dict[str, str])
async def submit_crawl_endpoint(request: StartCrawlRequest, current_user: Annotated[User, Depends(get_current_user)]):
    """
    Submits a crawl job to the distributed queue system.
    """
    logger.info(f"API: Received request to submit crawl for {request.target_url} by user: {current_user.username}.")
    return await submit_crawl_to_queue(request)

@queue_router.post("/test/submit_sample_job", response_model=Dict[str, str])
async def submit_sample_job_endpoint(current_user: Annotated[User, Depends(get_current_user)]):
    """
    Submit a sample crawl job for testing the queue system.
    """
    logger.info(f"API: Received request to submit sample job by user: {current_user.username}.")
    sample_request = StartCrawlRequest(
        target_url="https://example.com/sample",
        initial_seed_urls=["https://example.com/sample/page1"]
    )
    return await submit_crawl_to_queue(sample_request)

@queue_router.post("/schedule/crawl", response_model=Dict[str, str])
async def schedule_crawl_endpoint(request: StartCrawlRequest, current_user: Annotated[User, Depends(get_current_user)]):
    """
    Schedule a crawl job to run at a specific time or on a recurring basis.
    Note: Scheduling functionality needs to be implemented in the job submission service.
    """
    logger.info(f"API: Received request to schedule job for {request.target_url} by user: {current_user.username}.")
    if not request.scheduled_at and not request.cron_schedule:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Either 'scheduled_at' or 'cron_schedule' must be provided for scheduling.")
    
    if request.cron_schedule and not request.scheduled_at:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="For recurring jobs, 'scheduled_at' must be provided for the initial run time.")

    return await submit_crawl_to_queue(request)

@queue_router.get("/job_status/{job_id}", response_model=JobStatusResponse)
async def get_job_status_endpoint(job_id: str, current_user: Annotated[User, Depends(get_current_user)]):
    """
    Retrieves the current status of a specific crawling job.
    """
    logger.info(f"API: Received request for job status for job_id: {job_id} by user: {current_user.username}.")
    job_coordinator = await get_coordinator()
    job = await job_coordinator.get_job_status(job_id)

    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
    
    # Convert CrawlJob dataclass to JobStatusResponse Pydantic model
    return JobStatusResponse(
        job_id=job.id,
        status=job.status,
        progress_percentage=job.progress_percentage,
        message=job.status.value, # Using status value as a simple message
        errors=[f"{err.error_type}: {err.message}" for err in job.error_log],
        results_summary=job.results,
        last_updated=job.last_updated
    )

@queue_router.get("/stats", response_model=QueueStatsResponse)
async def get_stats_endpoint(current_user: Annotated[User, Depends(get_current_user)]):
    """
    Retrieves statistics about the job queue and connected crawlers.
    """
    logger.info(f"API: Received request for queue stats by user: {current_user.username}.")
    job_coordinator = await get_coordinator()
    stats = await job_coordinator.get_queue_stats()

    # Ensure datetime objects are isoformatted for JSON serialization
    # The `satellite_crawlers` in QueueStatsResponse is Dict[str, Any], so direct assignment is fine.
    # The `timestamp` in QueueStatsResponse is datetime, so direct assignment is fine.
    return QueueStatsResponse(
        pending_jobs=stats.get("pending_jobs", 0),
        results_pending=stats.get("results_pending", 0),
        active_satellites=stats.get("active_crawlers", 0),
        satellite_crawlers=stats.get("satellite_crawlers", {}), # This is already Dict[str, Any] with isoformatted timestamps
        timestamp=datetime.now()
    )

@queue_router.get("/crawler_health", response_model=List[CrawlerHealthResponse])
async def get_health_endpoint(current_user: Annotated[User, Depends(get_current_user)]):
    """
    Retrieves detailed health information for all satellite crawlers.
    """
    logger.info(f"API: Received request for crawler health by user: {current_user.username}.")
    job_coordinator = await get_coordinator()
    stats = await job_coordinator.get_queue_stats()

    crawler_health_list = []
    for crawler_id, details in stats.get("satellite_crawlers", {}).items():
        # Ensure datetime objects are correctly parsed from ISO format strings if they come that way
        last_seen_dt = details.get("last_seen")
        if isinstance(last_seen_dt, str):
            try:
                last_seen_dt = datetime.fromisoformat(last_seen_dt)
            except ValueError:
                logger.warning(f"Could not parse last_seen string: {details.get('last_seen')}")
                last_seen_dt = datetime.min # Fallback

        crawler_health_list.append(CrawlerHealthResponse(
            crawler_id=crawler_id,
            status=details.get("status", "UNKNOWN"),
            last_seen=last_seen_dt,
            cpu_usage=details.get("cpu_usage", 0.0),
            memory_usage=details.get("memory_usage", 0.0),
            jobs_processed=details.get("jobs_processed", 0),
            current_job_id=details.get("current_job_id"),
            error_rate=details.get("error_rate", 0.0),
            uptime_seconds=details.get("uptime_seconds", 0.0)
        ))
    return crawler_health_list
