import logging
import asyncio
import os
from datetime import datetime
from typing import Annotated, Dict, Any, Optional, List

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Response

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
from Link_Profiler.api.dependencies import get_current_user

# Import queue-related functions and models
from Link_Profiler.api.queue_endpoints import submit_crawl_to_queue, QueueCrawlRequest

# Import Prometheus metrics
from Link_Profiler.monitoring.prometheus_metrics import JOBS_CREATED_TOTAL

# Import core models
from Link_Profiler.core.models import User, CrawlStatus, ReportJob


reports_router = APIRouter(prefix="/api/reports", tags=["Reports"])

@reports_router.post("/schedule", response_model=Dict[str, str], status_code=status.HTTP_202_ACCEPTED)
async def schedule_report_generation_job(
    request: ReportScheduleRequest,
    background_tasks: BackgroundTasks,
    current_user: Annotated[User, Depends(get_current_user)]
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

    return await submit_crawl_to_queue(queue_request)

@reports_router.get("/{job_id}", response_model=ReportJobResponse)
async def get_report_job_status(job_id: str, current_user: Annotated[User, Depends(get_current_user)]):
    """
    Retrieves the status of a scheduled or generated report job.
    """
    logger.info(f"API: Received request for report job status {job_id} by user: {current_user.username}.")
    try:
        report_job = db.get_report_job(job_id)
        if not report_job:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report job not found.")
        return ReportJobResponse.from_report_job(report_job)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"API: Error retrieving report job status {job_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to retrieve report job status: {e}")

@reports_router.get("/{job_id}/download")
async def download_report_file(job_id: str, current_user: Annotated[User, Depends(get_current_user)]):
    """
    Downloads the generated report file for a completed report job.
    """
    logger.info(f"API: Received request to download report for job {job_id} by user: {current_user.username}.")
    try:
        report_job = db.get_report_job(job_id)
        if not report_job:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report job not found.")
        if report_job.status != CrawlStatus.COMPLETED:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Report job is not yet completed.")
        if not report_job.file_path or not os.path.exists(report_job.file_path):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report file not found on server.")
        
        file_content = await asyncio.to_thread(lambda: open(report_job.file_path, "rb").read())
        filename = os.path.basename(report_job.file_path)
        media_type = "application/pdf" if report_job.format == "pdf" else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" # For .xlsx
        
        return Response(content=file_content, media_type=media_type, headers={"Content-Disposition": f"attachment; filename={filename}"})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"API: Error downloading report for job {job_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to download report: {e}")
