from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional
from datetime import datetime
import logging

from Link_Profiler.database.database import Database
from Link_Profiler.core.models import CrawlStatus, CrawlJob
from Link_Profiler.api.schemas import CrawlJobResponse
from Link_Profiler.api.queue_endpoints import get_coordinator
from Link_Profiler.config.config_loader import ConfigLoader # Import ConfigLoader

# Initialize config_loader and db here, similar to main.py, but ensure it's robust
# This is a simplified approach for a router; in a larger app, these might be passed via dependency injection
# or a more sophisticated global state management.
try:
    from Link_Profiler.main import db, config_loader, logger
except ImportError:
    # Fallback for testing or if main.py is not yet fully initialized
    # This should ideally be avoided in production by ensuring proper app startup order
    logger = logging.getLogger(__name__)
    logging.basicConfig(level=logging.INFO)
    
    class DummyDB:
        def get_all_crawl_jobs(self) -> List[CrawlJob]:
            logger.warning("Using DummyDB in public_jobs.py. Database not properly initialized.")
            # Return some dummy data for testing purposes
            return [
                CrawlJob(
                    id="dummy_job_1",
                    target_url="https://dummy.com",
                    job_type="backlink_discovery",
                    status=CrawlStatus.COMPLETED,
                    created_date=datetime.now(),
                    progress_percentage=100.0,
                    urls_crawled=10,
                    links_found=5,
                    errors_count=0
                ),
                CrawlJob(
                    id="dummy_job_2",
                    target_url="https://test.org",
                    job_type="technical_audit",
                    status=CrawlStatus.IN_PROGRESS,
                    created_date=datetime.now(),
                    progress_percentage=50.0,
                    urls_crawled=20,
                    links_found=0,
                    errors_count=1
                )
            ]
    db = DummyDB()

    class DummyConfigLoader:
        def get(self, key, default=None):
            return default
    config_loader = DummyConfigLoader()


public_jobs_router = APIRouter()

@public_jobs_router.get("/public/jobs", response_model=List[CrawlJobResponse])
async def public_jobs(
    status_filter: Optional[CrawlStatus] = Query(None, description="Filter jobs by status")
):
    """
    Public endpoint to retrieve a list of all crawl jobs, optionally filtered by status,
    without authentication.
    """
    logger.info(f"API: Received request for public jobs with status filter: {status_filter}")
    try:
        all_jobs = db.get_all_crawl_jobs()
        if status_filter:
            filtered_jobs = [job for job in all_jobs if job.status == status_filter]
        else:
            filtered_jobs = all_jobs
        
        # Sort by created_date descending
        sorted_jobs = sorted(filtered_jobs, key=lambda job: job.created_date if job.created_date else datetime.min, reverse=True)
        
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

