import json
import logging
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
import asyncio # Import asyncio

import redis.asyncio as redis
from pydantic import BaseModel, Field

# Import core models
from Link_Profiler.core.models import CrawlJob, CrawlStatus, CrawlConfig, serialize_model
# Import CrawlConfigRequest from schemas for accurate type hinting
from Link_Profiler.api.schemas import CrawlConfigRequest, StartCrawlRequest # Import StartCrawlRequest as well

# Import job coordinator and its dependencies
from Link_Profiler.queue_system.job_coordinator import JobCoordinator
from Link_Profiler.config.config_loader import ConfigLoader
from Link_Profiler.database.database import Database
from Link_Profiler.services.alert_service import AlertService
from Link_Profiler.utils.connection_manager import ConnectionManager

# Get logger directly for this module
logger = logging.getLogger(__name__)

# Global variables to hold initialized dependencies for JobCoordinator
_redis_client: Optional[redis.Redis] = None
_config_loader: Optional[ConfigLoader] = None
_db: Optional[Database] = None
_alert_service_instance: Optional[AlertService] = None
_connection_manager: Optional[ConnectionManager] = None
_job_coordinator: Optional[JobCoordinator] = None

# Check for croniter explicitly if it's a core dependency for queue functionality
try:
    import croniter
    QUEUE_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Queue system not fully available: {e}. Scheduling features may be limited.")
    QUEUE_AVAILABLE = False

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
async def submit_crawl_to_queue(request: StartCrawlRequest) -> Dict[str, str]: # Use StartCrawlRequest for request type hint
    """
    Submits a crawl job to the Redis queue.
    """
    job_id = str(uuid.uuid4())
    
    # Explicitly extract attributes from CrawlConfigRequest into a dictionary
    # This is the most robust way to ensure a plain dictionary is passed.
    if request.config is not None:
        # Manually extract attributes to ensure compatibility
        crawl_config_kwargs = {
            "max_depth": request.config.max_depth,
            "max_pages": request.config.max_pages,
            "delay_seconds": request.config.delay_seconds,
            "timeout_seconds": request.config.timeout_seconds,
            "user_agent": request.config.user_agent,
            "respect_robots_txt": request.config.respect_robots_txt,
            "follow_redirects": request.config.follow_redirects,
            "extract_images": request.config.extract_images,
            "extract_pdfs": request.config.extract_pdfs,
            "max_file_size_mb": request.config.max_file_size_mb,
            "allowed_domains": request.config.allowed_domains,
            "blocked_domains": request.config.blocked_domains,
            "custom_headers": request.config.custom_headers,
            "max_retries": request.config.max_retries,
            "retry_delay_seconds": request.config.retry_delay_seconds,
            "user_agent_rotation": request.config.user_agent_rotation,
            "request_header_randomization": request.config.request_header_randomization,
            "human_like_delays": request.config.human_like_delays,
            "stealth_mode": request.config.stealth_mode,
            "browser_fingerprint_randomization": request.config.browser_fingerprint_randomization,
            "ml_rate_optimization": request.config.ml_rate_optimization,
            "captcha_solving_enabled": request.config.captcha_solving_enabled,
            "anomaly_detection_enabled": request.config.anomaly_detection_enabled,
            "use_proxies": request.config.use_proxies,
            "proxy_list": request.config.proxy_list,
            "proxy_region": request.config.proxy_region,
            "render_javascript": request.config.render_javascript,
            "browser_type": request.config.browser_type,
            "headless_browser": request.config.headless_browser,
            "extract_image_text": request.config.extract_image_text,
            "crawl_web3_content": request.config.crawl_web3_content,
            "crawl_social_media": request.config.crawl_social_media,
            # Ensure job_type is passed from the request's config
            "job_type": request.config.job_type if hasattr(request.config, 'job_type') else "unknown" # Add job_type explicitly
        }
    else:
        # If no config is provided, use default values or an empty dict
        # Note: CrawlConfig dataclass has default values, so an empty dict is fine.
        crawl_config_kwargs = {} 
    
    # Create a CrawlConfig object from the dictionary
    # The CrawlConfig dataclass will handle default values for missing keys
    crawl_config = CrawlConfig(**crawl_config_kwargs)

    # Create a CrawlJob object
    job = CrawlJob(
        id=job_id,
        target_url=request.target_url,
        job_type=crawl_config.job_type, # Use job_type from config
        status=CrawlStatus.PENDING,
        created_date=datetime.now(),
        config=crawl_config, # Pass the CrawlConfig object directly
        initial_seed_urls=request.initial_seed_urls,
        priority=request.priority,
        scheduled_at=request.scheduled_at,
        cron_schedule=request.cron_schedule
    )

    job_coordinator = await get_coordinator()
    await job_coordinator.submit_crawl_job(job)
    logger.info(f"Job {job_id} ({job.job_type}) submitted to queue for {request.target_url}.")
    return {"job_id": job_id, "status": "Job submitted to queue."}
