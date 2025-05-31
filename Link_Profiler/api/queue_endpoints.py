"""
Queue System API Extensions for Link Profiler
Add these endpoints to your main API or import this module
"""
import asyncio
from fastapi import HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from datetime import datetime
import logging
from uuid import uuid4

# Import the queue coordinator and core models
from Link_Profiler.queue_system.job_coordinator import JobCoordinator # Moved outside try-except
from Link_Profiler.core.models import CrawlConfig, CrawlJob, CrawlStatus, serialize_model
from Link_Profiler.database.database import Database # Import Database
from Link_Profiler.services.alert_service import AlertService # New: Import AlertService
from Link_Profiler.utils.connection_manager import ConnectionManager # New: Import ConnectionManager

try:
    # This flag indicates if the queue system's core components are available
    # (e.g., if croniter is installed, which is a dependency for JobCoordinator)
    import croniter # Check for croniter explicitly if it's a core dependency for queue functionality
    QUEUE_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Queue system not fully available: {e}. Scheduling features may be limited.")
    QUEUE_AVAILABLE = False


logger = logging.getLogger(__name__)

# Global coordinator instance
coordinator: Optional[JobCoordinator] = None

async def get_coordinator(db_instance: Database, alert_service_instance: Optional[AlertService] = None, connection_manager_instance: Optional[ConnectionManager] = None) -> JobCoordinator:
    """Get or create job coordinator instance"""
    global coordinator
    if not QUEUE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Queue system not available")
    
    if coordinator is None:
        coordinator = JobCoordinator(database=db_instance, alert_service=alert_service_instance, connection_manager=connection_manager_instance) # Pass the database, alert_service, and connection_manager instance
        await coordinator.__aenter__()
        
        # Start background tasks
        asyncio.create_task(coordinator.process_results())
        asyncio.create_task(coordinator.monitor_satellites())
        asyncio.create_task(coordinator._process_scheduled_jobs()) # New: Start scheduled jobs processor
    
    return coordinator

# Pydantic models for queue operations
class QueueCrawlRequest(BaseModel):
    target_url: str = Field(..., description="The URL for which to find backlinks")
    initial_seed_urls: List[str] = Field(..., description="URLs to start crawling from")
    config: Optional[Dict] = Field(None, description="Optional crawl configuration")
    priority: int = Field(5, description="Job priority (1-10, higher = more priority)")
    
    # New fields for scheduling
    scheduled_at: Optional[datetime] = Field(None, description="Specific UTC datetime to run the job (ISO format). If set, job is scheduled.")
    cron_schedule: Optional[str] = Field(None, description="Cron string for recurring jobs (e.g., '0 0 * * *'). Requires scheduled_at for first run.")

class QueueStatsResponse(BaseModel):
    pending_jobs: int
    active_crawlers: int
    total_jobs: int
    completed_jobs: int
    satellite_crawlers: List[Dict]

class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    progress_percentage: float
    urls_crawled: int
    links_found: int
    created_date: str
    started_date: Optional[str] = None
    completed_date: Optional[str] = None

# Queue endpoint functions that can be added to any FastAPI app
async def submit_crawl_to_queue(request: QueueCrawlRequest):
    """Submit a crawl job to the distributed queue system"""
    try:
        # The db and alert_service instances are passed to get_coordinator in add_queue_endpoints
        # Pass None for db_instance, alert_service_instance, and connection_manager_instance here, as they are initialized in startup
        coord = await get_coordinator(None, None, None) 
        
        # Convert config dict to CrawlConfig if provided
        crawl_config_obj = CrawlConfig.from_dict(request.config if request.config else {})
        
        # Create a CrawlJob object
        job_id = str(uuid4())
        job_type = request.config.get("job_type", "backlink_discovery") # Default to backlink_discovery
        
        job = CrawlJob(
            id=job_id,
            target_url=request.target_url,
            job_type=job_type,
            status=CrawlStatus.PENDING,
            priority=request.priority,
            created_date=datetime.now(), # Ensure created_date is set here
            scheduled_at=request.scheduled_at, # Pass scheduled_at
            cron_schedule=request.cron_schedule, # Pass cron_schedule
            config=serialize_model(crawl_config_obj), # Store serialized config
            # Pass initial_seed_urls, keyword, etc. within the config dict for the satellite to use
            # The satellite will deserialize this config and pass it to CrawlService.execute_predefined_job
            # For backlink_discovery, initial_seed_urls is directly from request
            # For other job types, specific parameters are passed in request.config
            # e.g., {"keyword": "...", "num_results": "...", "job_type": "serp_analysis"}
            # The satellite's _execute_crawl_job will extract these from job.config
        )
        
        # Add initial_seed_urls to job.config for backlink_discovery jobs
        if job_type == "backlink_discovery":
            job.config["initial_seed_urls"] = request.initial_seed_urls
        
        # Submit the CrawlJob object to the coordinator
        await coord.submit_crawl_job(job)
        
        return {"job_id": job_id, "status": "submitted", "message": "Job queued for processing"}
        
    except Exception as e:
        logger.error(f"Error submitting job to queue: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to submit job: {e}")

async def get_queue_job_status(job_id: str):
    """Get the current status of a queued crawl job"""
    try:
        # The db and alert_service instances are passed to get_coordinator in add_queue_endpoints
        # Pass None for db_instance, alert_service_instance, and connection_manager_instance here, as they are initialized in startup
        coord = await get_coordinator(None, None, None) 
        job = await coord.get_job_status(job_id)
        
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        return JobStatusResponse(
            job_id=job.id,
            status=job.status.value,
            progress_percentage=job.progress_percentage,
            urls_crawled=job.urls_crawled,
            links_found=job.links_found,
            created_date=job.created_date.isoformat(),
            started_date=job.started_date.isoformat() if job.started_date else None,
            completed_date=job.completed_date.isoformat() if job.completed_date else None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting job status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get job status: {e}")

async def get_queue_stats():
    """Get current queue and crawler statistics"""
    try:
        # The db and alert_service instances are passed to get_coordinator in add_queue_endpoints
        # Pass None for db_instance, alert_service_instance, and connection_manager_instance here, as they are initialized in startup
        coord = await get_coordinator(None, None, None) 
        stats = await coord.get_queue_stats()
        
        # Format satellite crawler info
        satellite_info = []
        for crawler_id, last_seen in coord.satellite_crawlers.items():
            satellite_info.append({
                "crawler_id": crawler_id,
                "last_seen": last_seen.isoformat(),
                "status": "healthy" if (datetime.now() - last_seen).total_seconds() < 60 else "stale"
            })
        
        return QueueStatsResponse(
            pending_jobs=stats["pending_jobs"],
            active_crawlers=stats["active_crawlers"],
            total_jobs=stats["total_jobs"],
            completed_jobs=stats["completed_jobs"],
            satellite_crawlers=satellite_info
        )
        
    except Exception as e:
        logger.error(f"Error getting queue stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get queue stats: {e}")

async def get_crawler_health():
    """Get detailed health information for all satellite crawlers"""
    try:
        # The db and alert_service instances are passed to get_coordinator in add_queue_endpoints
        # Pass None for db_instance, alert_service_instance, and connection_manager_instance here, as they are initialized in startup
        coord = await get_coordinator(None, None, None) 
        
        health_info = []
        for crawler_id, last_seen in coord.satellite_crawlers.items():
            # Calculate time since last heartbeat
            time_diff = datetime.now() - last_seen
            
            health_info.append({
                "crawler_id": crawler_id,
                "last_heartbeat": last_seen.isoformat(),
                "seconds_since_heartbeat": time_diff.total_seconds(),
                "status": "healthy" if time_diff.total_seconds() < 60 else "stale"
            })
        
        return {
            "total_crawlers": len(health_info),
            "healthy_crawlers": len([c for c in health_info if c["status"] == "healthy"]),
            "crawlers": health_info
        }
        
    except Exception as e:
        logger.error(f"Error getting crawler health: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get crawler health: {e}")

# Function to add queue endpoints to an existing FastAPI app
def add_queue_endpoints(app, db_instance: Database, alert_service_instance: Optional[AlertService] = None, connection_manager_instance: Optional[ConnectionManager] = None): # Accept db_instance, alert_service_instance, and connection_manager_instance
    """Add queue endpoints to an existing FastAPI app"""
    
    @app.post("/queue/submit_crawl", response_model=Dict[str, str])
    async def submit_crawl_endpoint(request: QueueCrawlRequest):
        """Submit a crawl job to the distributed queue system"""
        return await submit_crawl_to_queue(request)

    @app.get("/queue/job_status/{job_id}", response_model=JobStatusResponse)
    async def get_job_status_endpoint(job_id: str):
        """Get the current status of a queued crawl job"""
        return await get_queue_job_status(job_id)

    @app.get("/queue/stats", response_model=QueueStatsResponse)
    async def get_stats_endpoint():
        """Get current queue and crawler statistics"""
        return await get_queue_stats()

    @app.get("/queue/manage/crawler_health")
    async def get_health_endpoint():
        """Get detailed health information for all satellite crawlers"""
        return await get_crawler_health()

    @app.post("/queue/test/submit_sample_job")
    async def submit_sample_job_endpoint():
        """Submit a sample crawl job for testing the queue system"""
        sample_request = QueueCrawlRequest(
            target_url="https://example.com/sample",
            initial_seed_urls=["https://example.com/sample/page1"],
            priority=7
        )
        return await submit_crawl_to_queue(sample_request)

    # New: Endpoint for scheduling jobs
    @app.post("/schedule/crawl", response_model=Dict[str, str])
    async def schedule_crawl_endpoint(request: QueueCrawlRequest):
        """
        Schedule a crawl job to run at a specific time or on a recurring basis.
        Requires 'scheduled_at' for one-time scheduling or 'cron_schedule' for recurring.
        """
        if not request.scheduled_at and not request.cron_schedule:
            raise HTTPException(status_code=400, detail="Either 'scheduled_at' or 'cron_schedule' must be provided for scheduling.")
        
        if request.cron_schedule and not request.scheduled_at:
            # For recurring jobs, scheduled_at should be the first run time
            raise HTTPException(status_code=400, detail="For recurring jobs, 'scheduled_at' must be provided for the initial run time.")

        logger.info(f"Received request to schedule job for {request.target_url} at {request.scheduled_at} with cron '{request.cron_schedule}'.")
        return await submit_crawl_to_queue(request)


    # Add startup/shutdown events for coordinator
    @app.on_event("startup")
    async def startup_queue_coordinator():
        """Initialize the job coordinator on startup"""
        if QUEUE_AVAILABLE:
            logger.info("Initializing job coordinator...")
            try:
                await get_coordinator(db_instance, alert_service_instance, connection_manager_instance) # Pass db_instance, alert_service_instance, and connection_manager_instance here
                logger.info("Job coordinator initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize job coordinator: {e}", exc_info=True)

    @app.on_event("shutdown")
    async def shutdown_queue_coordinator():
        """Cleanup coordinator on shutdown"""
        global coordinator
        if coordinator:
            await coordinator.__aexit__(None, None, None)
            logger.info("Job coordinator shut down successfully")
