import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import asyncio

import redis.asyncio as redis
from pydantic import BaseModel, Field

# Import core models
from Link_Profiler.core.models import CrawlJob, CrawlStatus, CrawlConfig, serialize_model

# Import job coordinator
from Link_Profiler.queue_system.job_coordinator import JobCoordinator
from Link_Profiler.config.config_loader import ConfigLoader # Import ConfigLoader
from Link_Profiler.database.database import Database # Import Database
from Link_Profiler.services.alert_service import AlertService # Import AlertService
from Link_Profiler.utils.connection_manager import ConnectionManager # Import ConnectionManager


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


# --- Pydantic Models for Queue Requests ---
class QueueCrawlRequest(BaseModel):
    """
    Represents a request to submit a crawl job to the queue.
    This is a simplified version of CrawlJob for API submission.
    """
    target_url: str = Field(..., description="The URL to crawl or target for analysis.")
    initial_seed_urls: List[str] = Field(default_factory=list, description="Initial URLs to start crawling from.")
    config: Dict[str, Any] = Field(default_factory=dict, description="Configuration parameters for the job.")
    priority: int = Field(5, ge=1, le=10, description="Priority of the job (1=highest, 10=lowest).")
    scheduled_at: Optional[datetime] = Field(None, description="Optional: UTC datetime to schedule the job for.")
    cron_schedule: Optional[str] = Field(None, description="Optional: Cron string for recurring jobs.")


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
async def submit_crawl_to_queue(request: QueueCrawlRequest) -> Dict[str, str]:
    """
    Submits a crawl job to the Redis queue.
    """
    job_id = str(uuid.uuid4())
    
    # Create a CrawlConfig object from the request config dictionary
    crawl_config = CrawlConfig(**request.config)

    # Create a CrawlJob object
    job = CrawlJob(
        id=job_id,
        target_url=request.target_url,
        job_type=crawl_config.job_type, # Use job_type from config
        status=CrawlStatus.PENDING,
        created_date=datetime.now(),
        config=crawl_config,
        initial_seed_urls=request.initial_seed_urls,
        priority=request.priority,
        scheduled_at=request.scheduled_at,
        cron_schedule=request.cron_schedule
    )

    job_coordinator = await get_coordinator()
    await job_coordinator.submit_crawl_job(job)
    logger.info(f"Job {job_id} ({job.job_type}) submitted to queue for {request.target_url}.")
    return {"job_id": job_id, "status": "Job submitted to queue."}
