from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional
from datetime import datetime
import logging

from Link_Profiler.database.database import Database
from Link_Profiler.core.models import CrawlStatus, CrawlJob, User
from Link_Profiler.api.schemas import CrawlJobResponse
from Link_Profiler.api.queue_endpoints import get_coordinator
from Link_Profiler.config.config_loader import ConfigLoader
from Link_Profiler.api.dependencies import get_current_user

# Initialize config_loader and db here
try:
    from Link_Profiler.main import db, config_loader, logger
except ImportError:
    # Fallback for testing or if main.py is not yet fully initialized
    logger = logging.getLogger(__name__)
    logging.basicConfig(level=logging.INFO)
    
    class DummyDB:
        def get_all_crawl_jobs(self) -> List[CrawlJob]:
            logger.warning("Using DummyDB in public_jobs.py. Database not properly initialized.")
            return []
    db = DummyDB()

    class DummyConfigLoader:
        def get(self, key, default=None):
            return default
    config_loader = DummyConfigLoader()


public_jobs_router = APIRouter()

# Remove sensitive public endpoints and require authentication

@public_jobs_router.get("/public/status")
async def public_status():
    """
    Minimal public status endpoint - only shows if service is up
    """
    return {
        "status": "operational",
        "service": "Link Profiler API",
        "timestamp": datetime.now().isoformat()
    }

# All job-related endpoints now require authentication
@public_jobs_router.get("/api/jobs/all", response_model=List[CrawlJobResponse])
async def get_all_jobs_authenticated(
    status_filter: Optional[str] = Query(None, description="Filter jobs by status"),
    current_user: User = Depends(get_current_user)
):
    """
    Get all jobs - requires authentication and admin privileges
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Admin privileges required"
        )
    
    logger.info(f"Admin {current_user.username} requested all jobs with status filter: {status_filter}")
    
    try:
        # Handle empty string status filter
        if status_filter == "":
            status_filter = None
            
        all_jobs = db.get_all_crawl_jobs()
        
        if status_filter:
            try:
                filter_status = CrawlStatus[status_filter.upper()]
                all_jobs = [job for job in all_jobs if job.status == filter_status]
            except KeyError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, 
                    detail=f"Invalid status_filter: {status_filter}. Must be one of {list(CrawlStatus.__members__.keys())}"
                )
        
        # Sort by created_date descending
        sorted_jobs = sorted(all_jobs, key=lambda job: job.created_date if job.created_date else datetime.min, reverse=True)
        
        return [CrawlJobResponse.from_crawl_job(job) for job in sorted_jobs]
        
    except Exception as e:
        logger.error(f"Error retrieving jobs for admin {current_user.username}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail="Failed to retrieve crawl jobs"
        )

@public_jobs_router.get("/api/jobs/paused")
async def get_jobs_paused_status(current_user: User = Depends(get_current_user)):
    """
    Check if job processing is paused - requires authentication and admin privileges
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Admin privileges required"
        )
    
    logger.info(f"Admin {current_user.username} requested job pause status.")
    
    try:
        coordinator = await get_coordinator()
        is_paused = await coordinator.is_paused()
        return {"is_paused": is_paused}
    except Exception as e:
        logger.error(f"Error checking job pause status for admin {current_user.username}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail="Failed to retrieve job pause status"
        )

@public_jobs_router.post("/api/jobs/pause")
async def pause_jobs(current_user: User = Depends(get_current_user)):
    """
    Pause job processing - requires authentication and admin privileges
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Admin privileges required"
        )
    
    logger.info(f"Admin {current_user.username} requested to pause job processing.")
    
    try:
        coordinator = await get_coordinator()
        await coordinator.pause_processing()
        return {"status": "paused", "message": "Job processing has been paused"}
    except Exception as e:
        logger.error(f"Error pausing jobs for admin {current_user.username}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail="Failed to pause job processing"
        )

@public_jobs_router.post("/api/jobs/resume")
async def resume_jobs(current_user: User = Depends(get_current_user)):
    """
    Resume job processing - requires authentication and admin privileges
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Admin privileges required"
        )
    
    logger.info(f"Admin {current_user.username} requested to resume job processing.")
    
    try:
        coordinator = await get_coordinator()
        await coordinator.resume_processing()
        return {"status": "resumed", "message": "Job processing has been resumed"}
    except Exception as e:
        logger.error(f"Error resuming jobs for admin {current_user.username}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail="Failed to resume job processing"
        )