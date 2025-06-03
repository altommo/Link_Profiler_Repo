import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import asyncio # Added missing import

import redis.asyncio as redis
from pydantic import BaseModel, Field

# Import core models
from Link_Profiler.core.models import CrawlJob, CrawlStatus, CrawlConfig, serialize_model

# Import job coordinator
from Link_Profiler.queue_system.job_coordinator import JobCoordinator

# Get logger and global instances from main.py
# These are expected to be initialized in main.py before this module is imported
try:
    from Link_Profiler.main import logger, redis_client, config_loader, db, alert_service_instance, connection_manager
except ImportError:
    logger = logging.getLogger(__name__)
    logging.basicConfig(level=logging.INFO)
    # Fallback for testing or if main.py is not yet fully initialized
    redis_client = None
    config_loader = None
    db = None
    alert_service_instance = None
    connection_manager = None

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

async def get_coordinator() -> JobCoordinator:
    """
    Returns the singleton JobCoordinator instance.
    Initializes it if it hasn't been already.
    """
    global _job_coordinator
    if not QUEUE_AVAILABLE:
        logger.error("Queue system not available. Croniter might be missing.")
        raise RuntimeError("Queue system not available. Missing dependencies.") # Changed to RuntimeError as it's a core issue

    if _job_coordinator is None:
        if redis_client is None or config_loader is None or db is None or alert_service_instance is None or connection_manager is None:
            logger.error("JobCoordinator dependencies (redis_client, config_loader, db, alert_service_instance, connection_manager) are not initialized.")
            raise RuntimeError("JobCoordinator dependencies not available. Ensure main.py initializes them before importing queue_endpoints.")
        
        job_queue_name = config_loader.get("queue.job_queue_name", "crawl_jobs")
        result_queue_name = config_loader.get("queue.result_queue_name", "crawl_results")
        dead_letter_queue_name = config_loader.get("queue.dead_letter_queue_name", "dead_letters")
        satellite_heartbeat_prefix = config_loader.get("queue.satellite_heartbeat_prefix", "satellite_heartbeat:")
        satellite_timeout_seconds = config_loader.get("queue.satellite_timeout_seconds", 300)

        _job_coordinator = JobCoordinator(
            redis_client=redis_client,
            db=db,
            job_queue_name=job_queue_name,
            result_queue_name=result_queue_name,
            dead_letter_queue_name=dead_letter_queue_name,
            satellite_heartbeat_prefix=satellite_heartbeat_prefix,
            satellite_timeout_seconds=satellite_timeout_seconds,
            alert_service=alert_service_instance,
            connection_manager=connection_manager
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
