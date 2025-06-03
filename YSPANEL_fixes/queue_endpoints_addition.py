# Add this to the end of your existing queue_endpoints.py file

# --- Function to add queue endpoints to FastAPI app ---
def add_queue_endpoints(app):
    """
    Add queue-related endpoints to a FastAPI application.
    This function should be called during app initialization.
    """
    from fastapi import HTTPException
    
    @app.post("/queue/submit_crawl")
    async def submit_crawl_endpoint(request: QueueCrawlRequest):
        """Submit a crawl job to the queue"""
        try:
            result = await submit_crawl_to_queue(request)
            return result
        except Exception as e:
            logger.error(f"Error submitting crawl job: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/queue/stats")
    async def get_queue_stats():
        """Get queue statistics"""
        try:
            coordinator = await get_coordinator()
            stats = await coordinator.get_queue_stats()
            return stats
        except Exception as e:
            logger.error(f"Error getting queue stats: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/queue/job_status/{job_id}")
    async def get_job_status(job_id: str):
        """Get status of a specific job"""
        try:
            coordinator = await get_coordinator()
            status = await coordinator.get_job_status(job_id)
            return {"job_id": job_id, "status": status}
        except Exception as e:
            logger.error(f"Error getting job status: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/queue/manage/crawler_health")
    async def get_crawler_health():
        """Get health status of all satellite crawlers"""
        try:
            coordinator = await get_coordinator()
            health = await coordinator.get_crawler_health()
            return health
        except Exception as e:
            logger.error(f"Error getting crawler health: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/queue/test/submit_sample_job")
    async def submit_sample_job():
        """Submit a sample job for testing"""
        try:
            sample_request = QueueCrawlRequest(
                target_url="https://example.com",
                initial_seed_urls=["https://example.com"],
                config={
                    "job_type": "backlink_discovery",
                    "max_depth": 1,
                    "max_pages": 5,
                    "delay_seconds": 1.0
                },
                priority=5
            )
            result = await submit_crawl_to_queue(sample_request)
            return {"message": "Sample job submitted", "result": result}
        except Exception as e:
            logger.error(f"Error submitting sample job: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    logger.info("Queue endpoints added to FastAPI app")
