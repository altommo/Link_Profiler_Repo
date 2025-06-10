import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Annotated
import asyncio

import redis.asyncio as redis
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, status, Query

# Import core models
from Link_Profiler.core.models import CrawlJob, CrawlStatus, CrawlConfig, serialize_model, User
from Link_Profiler.api.schemas import CrawlJobResponse, QueueStatsResponse, JobStatusResponse, QueueCrawlRequest # Import schemas

# Import job coordinator
from Link_Profiler.queue_system.job_coordinator import JobCoordinator
from Link_Profiler.config.config_loader import ConfigLoader # Import ConfigLoader
from Link_Profiler.database.database import Database # Import Database
from Link_Profiler.services.alert_service import AlertService # Import AlertService
from Link_Profiler.utils.connection_manager import ConnectionManager # Import ConnectionManager

# Import decorators and data_service
from Link_Profiler.api.decorators import require_auth, cache_first_route
from Link_Profiler.services.data_service import data_service


logger = logging.getLogger(__name__)

# Global variables to hold initialized dependencies
_redis_client: Optional[redis.Redis] = None
_config_loader: Optional[ConfigLoader] = None
_db: Optional[Database] = None
_alert_service_instance: Optional[AlertService] = None
_connection_manager: Optional[ConnectionManager] = None

# Check for croniter explicitly if it's a core dependency for queue functionality
try:
    import croniter
    QUEUE_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Queue system not fully available: {e}. Scheduling features may be limited.")
    QUEUE_AVAILABLE = False


# --- Global Job Coordinator Instance ---
_job_coordinator: Optional[JobCoordinator] = None

def set_coordinator_dependencies(
    redis_client: redis.Redis,
    config_loader: ConfigLoader,
    db: Database,
    alert_service: AlertService,
    connection_manager: ConnectionManager
):
    """
    Sets the global dependencies for the JobCoordinator.
    This function should be called once during application startup.
    """
    global _redis_client, _config_loader, _db, _alert_service_instance, _connection_manager
    _redis_client = redis_client
    _config_loader = config_loader
    _db = db
    _alert_service_instance = alert_service
    _connection_manager = connection_manager
    logger.info("JobCoordinator dependencies set.")


async def get_coordinator() -> JobCoordinator:
    """
    Returns the singleton JobCoordinator instance.
    Initializes it if it hasn't been already.
    """
    global _job_coordinator
    if not QUEUE_AVAILABLE:
        logger.error("Queue system not available. Croniter might be missing.")
        raise RuntimeError("Queue system not available. Missing dependencies.")

    if _job_coordinator is None:
        if _redis_client is None or _config_loader is None or _db is None or _alert_service_instance is None or _connection_manager is None:
            logger.error("JobCoordinator dependencies (redis_client, config_loader, db, alert_service_instance, connection_manager) are not initialized.")
            raise RuntimeError("JobCoordinator dependencies not available. Ensure set_coordinator_dependencies() is called before get_coordinator().")
        
        _job_coordinator = JobCoordinator(
            redis_client=_redis_client,
            config_loader=_config_loader,
            database=_db,
            alert_service=_alert_service_instance,
            connection_manager=_connection_manager
        )
        # Start background tasks here, as this is the first time coordinator is accessed
        # This ensures tasks are started only once when the coordinator is first retrieved.
        await _job_coordinator.__aenter__() # Enter the context manager
        asyncio.create_task(_job_coordinator.process_results())
        asyncio.create_task(_job_coordinator.monitor_satellites())
        asyncio.create_task(_job_coordinator._process_scheduled_jobs())
        logger.info("JobCoordinator initialized and background tasks started.")
    return _job_coordinator

# --- Queue Submission Function ---
async def submit_crawl_to_queue(request: QueueCrawlRequest, user: User) -> Dict[str, str]:
    """
    Submits a crawl job to the Redis queue.
    """
    job_id = str(uuid.uuid4())
    
    # Create a CrawlConfig object from the request config dictionary
    # Ensure config is passed as a dictionary to CrawlJob
    crawl_config_dict = request.config if request.config is not None else {}
    
    # Create a CrawlJob object
    job = CrawlJob(
        id=job_id,
        target_url=request.target_url,
        job_type=crawl_config_dict.get('job_type', 'generic_crawl'), # Use job_type from config or default
        status=CrawlStatus.PENDING,
        created_at=datetime.now(), # Use created_at
        config=crawl_config_dict, # Pass as dict
        # initial_seed_urls is not part of CrawlJob dataclass directly, it's part of the request
        # If needed in CrawlJob, it should be added to its definition or stored in config/results
        priority=request.priority,
        scheduled_at=request.scheduled_at,
        cron_schedule=request.cron_schedule,
        user_id=user.id, # Set user_id from authenticated user
        organization_id=user.organization_id # Set organization_id from authenticated user
    )

    job_coordinator = await get_coordinator()
    await job_coordinator.submit_crawl_job(job)
    logger.info(f"Job {job_id} ({job.job_type}) submitted to queue for {request.target_url} by user {user.username}.")
    return {"job_id": job_id, "status": "Job submitted to queue."}


# --- FastAPI Router for Queue Endpoints ---
queue_router = APIRouter(prefix="/api/queue", tags=["Queue Management"])

@queue_router.post("/submit_crawl", response_model=Dict[str, str], status_code=status.HTTP_202_ACCEPTED)
@require_auth
async def submit_crawl_job_endpoint(request: QueueCrawlRequest, current_user: User):
    """
    Submits a new crawl job to the queue. Requires authentication.
    """
    # Admin check is handled by the route in monitoring_debug.py for now,
    # but for customer-facing APIs, this would be based on user roles/permissions.
    # For this refactor, we assume any authenticated user can submit.
    
    logger.info(f"User {current_user.username} submitting new crawl job for {request.target_url}.")
    try:
        response = await submit_crawl_to_queue(request, current_user)
        return response
    except Exception as e:
        logger.error(f"Error submitting crawl job: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to submit crawl job: {e}")

@queue_router.get("/stats", response_model=QueueStatsResponse)
@require_auth
async def get_queue_stats_endpoint(current_user: User):
    """
    Retrieves statistics about the job queues. Requires authentication.
    """
    # This endpoint is typically for admin/monitoring, so keeping direct coordinator call.
    # If customer-facing, it would need filtering by user_id/organization_id.
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required to view queue stats.")
    
    logger.info(f"Admin user {current_user.username} requesting queue stats.")
    try:
        coordinator = await get_coordinator()
        stats = await coordinator.get_queue_stats()
        # Ensure the stats dictionary matches QueueStatsResponse schema
        return QueueStatsResponse(**stats)
    except Exception as e:
        logger.error(f"Error retrieving queue stats: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to retrieve queue stats: {e}")

@queue_router.get("/job_status/{job_id}", response_model=CrawlJobResponse)
@require_auth
@cache_first_route
async def get_job_status_endpoint(
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
    Retrieves the status of a specific crawl job. Requires authentication.
    By default, data is served from cache. Use `?source=live` to fetch the latest data,
    subject to user permissions and configuration.
    """
    logger.info(f"User {current_user.username} requesting status for job ID: {job_id} (source: {source}).")
    try:
        job_data = await data_service.get_crawl_job_by_id(job_id, source=source, current_user=current_user)
        if not job_data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
        
        # Optional: Add authorization check here if jobs are user-specific
        # if job_data.get("user_id") != current_user.id and not current_user.is_admin:
        #     raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission to view this job.")

        return CrawlJobResponse(**job_data) # Use **job_data to unpack dict
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error retrieving job status for {job_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to retrieve job status: {e}")

@queue_router.post("/pause_processing", response_model=Dict[str, str])
@require_auth
async def pause_job_processing_endpoint(current_user: User):
    """
    Pauses job processing across all crawlers. Requires admin privileges.
    """
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required.")
    
    logger.info(f"Admin user {current_user.username} requesting to pause job processing.")
    try:
        coordinator = await get_coordinator()
        success = await coordinator.pause_job_processing()
        if success:
            return {"message": "Job processing paused successfully."}
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to pause job processing.")
    except Exception as e:
        logger.error(f"Error pausing job processing: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to pause job processing: {e}")

@queue_router.post("/resume_processing", response_model=Dict[str, str])
@require_auth
async def resume_job_processing_endpoint(current_user: User):
    """
    Resumes job processing across all crawlers. Requires admin privileges.
    """
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required.")
    
    logger.info(f"Admin user {current_user.username} requesting to resume job processing.")
    try:
        coordinator = await get_coordinator()
        success = await coordinator.resume_job_processing()
        if success:
            return {"message": "Job processing resumed successfully."}
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to resume job processing.")
    except Exception as e:
        logger.error(f"Error resuming job processing: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to resume job processing: {e}")

@queue_router.post("/cancel_job/{job_id}", response_model=Dict[str, str])
@require_auth
async def cancel_job_endpoint(job_id: str, current_user: User):
    """
    Cancels a specific job. Requires admin privileges.
    """
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required.")
    
    logger.info(f"Admin user {current_user.username} requesting to cancel job ID: {job_id}.")
    try:
        coordinator = await get_coordinator()
        success = await coordinator.cancel_job(job_id)
        if success:
            return {"message": f"Job {job_id} cancelled successfully."}
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to cancel job {job_id}.")
    except Exception as e:
        logger.error(f"Error cancelling job {job_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to cancel job {job_id}: {e}")

@queue_router.get("/processing_status", response_model=Dict[str, bool])
@require_auth
async def get_processing_status_endpoint(current_user: User):
    """
    Retrieves the current global job processing pause status. Requires authentication.
    """
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required.")
    
    logger.info(f"Admin user {current_user.username} requesting global processing status.")
    try:
        coordinator = await get_coordinator()
        is_paused = await coordinator.is_processing_paused()
        return {"is_paused": is_paused}
    except Exception as e:
        logger.error(f"Error retrieving processing status: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to retrieve processing status: {e}")
