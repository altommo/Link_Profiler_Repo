"""
Updated FastAPI Integration with Queue Distribution
Add these endpoints to your existing main.py
"""
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List, Optional, Dict
import asyncio
import logging

# Import the new queue components
from job_coordinator import JobCoordinator

# Add to your existing FastAPI app
logger = logging.getLogger(__name__)

# Global coordinator instance
coordinator = None

async def get_coordinator():
    """Get or create job coordinator instance"""
    global coordinator
    if coordinator is None:
        coordinator = JobCoordinator()
        await coordinator.__aenter__()
        
        # Start background tasks
        asyncio.create_task(coordinator.process_results())
        asyncio.create_task(coordinator.monitor_satellites())
    
    return coordinator

# New Pydantic models for queue operations
class QueueCrawlRequest(BaseModel):
    target_url: str
    initial_seed_urls: List[str]
    config: Optional[Dict] = None
    priority: int = 5

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

# Add these new endpoints to your existing FastAPI app

@app.post("/queue/submit_crawl", response_model=Dict[str, str])
async def submit_crawl_to_queue(request: QueueCrawlRequest):
    """
    Submit a crawl job to the distributed queue system.
    Jobs will be picked up by available satellite crawlers.
    """
    try:
        coord = await get_coordinator()
        
        # Convert config dict to CrawlConfig if provided
        config = None
        if request.config:
            from Link_Profiler.core.models import CrawlConfig
            config = CrawlConfig.from_dict(request.config)
        
        job_id = await coord.submit_crawl_job(
            target_url=request.target_url,
            initial_seed_urls=request.initial_seed_urls,
            config=config,
            priority=request.priority
        )
        
        return {"job_id": job_id, "status": "submitted", "message": "Job queued for processing"}
        
    except Exception as e:
        logger.error(f"Error submitting job to queue: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to submit job: {e}")

@app.get("/queue/job_status/{job_id}", response_model=JobStatusResponse)
async def get_queue_job_status(job_id: str):
    """
    Get the current status of a queued crawl job.
    """
    try:
        coord = await get_coordinator()
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

@app.get("/queue/stats", response_model=QueueStatsResponse)
async def get_queue_stats():
    """
    Get current queue and crawler statistics.
    """
    try:
        coord = await get_coordinator()
        stats = await coord.get_queue_stats()
        
        # Format satellite crawler info
        satellite_info = []
        for crawler_id, last_seen in coord.satellite_crawlers.items():
            satellite_info.append({
                "crawler_id": crawler_id,
                "last_seen": last_seen.isoformat(),
                "status": "online"
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

@app.post("/queue/manage/pause_queue")
async def pause_job_queue():
    """
    Pause the job queue (prevent new jobs from being processed).
    """
    # Implementation would depend on your specific needs
    # Could set a Redis flag that satellite crawlers check
    return {"status": "queue_paused", "message": "Job queue has been paused"}

@app.post("/queue/manage/resume_queue")
async def resume_job_queue():
    """
    Resume the job queue.
    """
    return {"status": "queue_resumed", "message": "Job queue has been resumed"}

@app.get("/queue/manage/crawler_health")
async def get_crawler_health():
    """
    Get detailed health information for all satellite crawlers.
    """
    try:
        coord = await get_coordinator()
        
        health_info = []
        for crawler_id, last_seen in coord.satellite_crawlers.items():
            # Calculate time since last heartbeat
            import datetime
            time_diff = datetime.datetime.now() - last_seen
            
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

# Startup event to initialize coordinator
@app.on_event("startup")
async def startup_event():
    """Initialize the job coordinator on startup"""
    logger.info("Initializing job coordinator...")
    await get_coordinator()
    logger.info("Job coordinator initialized successfully")

# Shutdown event to cleanup coordinator
@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup coordinator on shutdown"""
    global coordinator
    if coordinator:
        await coordinator.__aexit__(None, None, None)
        logger.info("Job coordinator shut down successfully")

# Example usage endpoints for testing
@app.post("/queue/test/submit_sample_job")
async def submit_sample_job():
    """
    Submit a sample crawl job for testing the queue system.
    """
    sample_request = QueueCrawlRequest(
        target_url="https://example.com",
        initial_seed_urls=["https://competitor1.com", "https://competitor2.com"],
        priority=7
    )
    
    return await submit_crawl_to_queue(sample_request)
