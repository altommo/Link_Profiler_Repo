import logging
import asyncio
import os
from datetime import datetime
from typing import Annotated, Dict, Any, Optional, List

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Response, Query

# Import globally initialized instances from main.py
try:
    from Link_Profiler.main import logger, db, config_loader
except ImportError:
    logger = logging.getLogger(__name__)
    logging.basicConfig(level=logging.INFO)
    # Dummy instances for testing or if main.py is not fully initialized
    class DummyDB:
        def get_report_job(self, job_id): return None
    db = DummyDB()
    class DummyConfigLoader:
        def get(self, key, default=None): return default
    config_loader = DummyConfigLoader()


# Import shared Pydantic models and dependencies
from Link_Profiler.api.schemas import (
    ReportScheduleRequest, ReportJobResponse
)
# Import decorators and data_service
from Link_Profiler.api.decorators import require_auth, cache_first_route
from Link_Profiler.services.data_service import data_service

# Import queue-related functions and models
from Link_Profiler.api.queue_endpoints import submit_crawl_to_queue, QueueCrawlRequest

# Import Prometheus metrics
from Link_Profiler.monitoring.prometheus_metrics import JOBS_CREATED_TOTAL

# Import core models
from Link_Profiler.core.models import User, CrawlStatus, ReportJob


reports_router = APIRouter(prefix="/api/reports", tags=["Reports"])

@reports_router.post("/schedule", response_model=Dict[str, str], status_code=status.HTTP_202_ACCEPTED)
@require_auth
async def schedule_report_generation_job(
    request: ReportScheduleRequest,
    background_tasks: BackgroundTasks,
    current_user: User # Injected by @require_auth
):
    """
    Schedules a report generation job to run at a specific time or on a recurring basis.
    """
    logger.info(f"API: Received request to schedule report '{request.report_type}' for '{request.target_identifier}' by user: {current_user.username}.")
    JOBS_CREATED_TOTAL.labels(job_type='report_generation').inc()

    if not request.scheduled_at and not request.cron_schedule:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Either 'scheduled_at' or 'cron_schedule' must be provided for scheduling.")
    
    if request.cron_schedule and not request.scheduled_at:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="For recurring reports, 'scheduled_at' must be provided for the initial run time.")

    queue_request = QueueCrawlRequest(
        target_url=request.target_identifier,
        initial_seed_urls=[],
        config=request.config if request.config else {},
        priority=5,
        scheduled_at=request.scheduled_at,
        cron_schedule=request.cron_schedule
    )
    queue_request.config["job_type"] = "report_generation"
    queue_request.config["report_job_type"] = request.report_type
    queue_request.config["report_target_identifier"] = request.target_identifier
    queue_request.config["report_format"] = request.format

    # Pass the current_user to submit_crawl_to_queue so user_id/organization_id can be set
    return await submit_crawl_to_queue(queue_request, current_user)

@reports_router.get("/{job_id}", response_model=ReportJobResponse)
@require_auth
@cache_first_route
async def get_report_job_status(
    job_id: str, 
    current_user: User, # Injected by @require_auth
    source: Annotated[Optional[str], Query(
        "cache", 
        description="""Data source for the request:
        - `cache`: Returns cached data (default, fastest response)
        - `live`: Returns real-time data (slower, requires appropriate user tier)""",
        enum=["cache", "live"],
        example="cache"
    )] = "cache"
):
    """
    Retrieves the status of a scheduled or generated report job.
    By default, data is served from cache. Use `?source=live` to fetch the latest data,
    subject to user permissions and configuration.
    """
    logger.info(f"API: User {current_user.username} requesting report job status {job_id} (source: {source}).")
    try:
        report_job_data = await data_service.get_report_job_by_id(job_id, source=source, current_user=current_user)
        if not report_job_data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report job not found.")
        
        # Optional: Add authorization check here if reports are user-specific
        # if report_job_data.get("user_id") != current_user.id and not current_user.is_admin:
        #     raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission to view this report job.")

        return ReportJobResponse(**report_job_data) # Use **report_job_data to unpack dict
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"API: Error retrieving report job status {job_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to retrieve report job status: {e}")

@reports_router.get("/{job_id}/download")
@require_auth
async def download_report_file(job_id: str, current_user: User): # Injected by @require_auth
    """
    Downloads the generated report file for a completed report job.
    """
    logger.info(f"API: User {current_user.username} requesting to download report for job {job_id}.")
    try:
        # Always fetch live for download to ensure we have the latest status and file path
        report_job_data = await data_service.get_report_job_by_id(job_id, source="live", current_user=current_user)
        
        if not report_job_data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report job not found.")
        
        # Optional: Add authorization check here if reports are user-specific
        # if report_job_data.get("user_id") != current_user.id and not current_user.is_admin:
        #     raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission to download this report.")

        # Convert dict to ReportJob dataclass for easier access to attributes
        report_job = ReportJob(**report_job_data)

        if report_job.status != CrawlStatus.COMPLETED:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Report job is not yet completed.")
        if not report_job.generated_file_path or not os.path.exists(report_job.generated_file_path):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report file not found on server.")
        
        file_content = await asyncio.to_thread(lambda: open(report_job.generated_file_path, "rb").read())
        filename = os.path.basename(report_job.generated_file_path)
        
        # Determine media type based on format
        media_type = "application/octet-stream" # Default
        if report_job.format == "pdf":
            media_type = "application/pdf"
        elif report_job.format == "xlsx":
            media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        elif report_job.format == "csv":
            media_type = "text/csv"
        elif report_job.format == "json":
            media_type = "application/json"
        
        return Response(content=file_content, media_type=media_type, headers={"Content-Disposition": f"attachment; filename={filename}"})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"API: Error downloading report for job {job_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to download report: {e}")
