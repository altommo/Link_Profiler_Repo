import logging
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from Link_Profiler.api.dependencies import get_current_user
from Link_Profiler.core.models import User, CrawlJob, CrawlStatus
from Link_Profiler.api.schemas import CrawlJobResponse, UserResponse, QueueCrawlRequest, CrawlConfigRequest # Import necessary schemas
from Link_Profiler.database.database import db # Import the database singleton
from Link_Profiler.api.queue_endpoints import submit_crawl_to_queue # Import the function to submit jobs

logger = logging.getLogger(__name__)

customer_router = APIRouter(prefix="/api/customer", tags=["Customer API"])

@customer_router.get("/profile", response_model=UserResponse)
async def get_customer_profile(current_user: User = Depends(get_current_user)):
    """
    Retrieve the authenticated customer's profile.
    """
    logger.info(f"Customer user {current_user.username} requesting their profile.")
    # The current_user object already contains the necessary profile data
    return UserResponse.from_user(current_user)

@customer_router.put("/profile", response_model=UserResponse)
async def update_customer_profile(user_update: UserResponse, current_user: User = Depends(get_current_user)):
    """
    Update the authenticated customer's profile.
    Note: This example allows updating email/username. In a real app,
    username might be immutable or require special handling.
    Password changes would be a separate endpoint.
    """
    logger.info(f"Customer user {current_user.username} updating their profile.")
    
    # Prevent changing ID or admin status via this endpoint
    if user_update.id != current_user.id or user_update.is_admin != current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot change user ID or admin status via this endpoint."
        )

    # Update fields from the request model
    current_user.username = user_update.username
    current_user.email = user_update.email
    current_user.is_active = user_update.is_active # Allow user to deactivate themselves? Or only admin?

    try:
        updated_user = db.update_user(current_user)
        return UserResponse.from_user(updated_user)
    except Exception as e:
        logger.error(f"Error updating profile for user {current_user.username}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update profile.")


@customer_router.get("/jobs", response_model=List[CrawlJobResponse])
async def get_customer_crawl_jobs(
    current_user: User = Depends(get_current_user),
    status_filter: Optional[str] = Query(None, description="Filter jobs by status (e.g., 'PENDING', 'IN_PROGRESS', 'COMPLETED', 'FAILED').")
):
    """
    Retrieve crawl jobs belonging to the authenticated customer.
    """
    logger.info(f"Customer user {current_user.username} requesting their crawl jobs.")
    
    try:
        # In a multi-tenant system, jobs would be associated with a user_id or organization_id.
        # For now, we'll simulate filtering by user_id if it were implemented in db.get_all_crawl_jobs.
        # Assuming db.get_all_crawl_jobs can take a user_id filter.
        # For this example, we'll fetch all and filter in memory, but this is inefficient for large datasets.
        all_jobs = db.get_all_crawl_jobs() # This currently gets ALL jobs, not just for the user.
                                           # This needs to be updated in database.py to filter by user_id.
        
        # Filter by user_id (placeholder logic, assuming CrawlJob has a user_id field)
        # For now, let's assume all jobs are visible to all authenticated users for simplicity,
        # but in a real multi-tenant system, this would be:
        # user_jobs = [job for job in all_jobs if job.user_id == current_user.id]
        user_jobs = all_jobs # TEMPORARY: Replace with actual user-specific job fetching

        if status_filter:
            try:
                filter_status_enum = CrawlStatus[status_filter.upper()]
                user_jobs = [job for job in user_jobs if job.status == filter_status_enum]
            except KeyError:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid status_filter: {status_filter}. Must be one of {list(CrawlStatus.__members__.keys())}.")
        
        # Sort by created date, newest first
        sorted_jobs = sorted(user_jobs, key=lambda job: job.created_at, reverse=True)
        
        return [CrawlJobResponse.from_crawl_job(job) for job in sorted_jobs]
    except Exception as e:
        logger.error(f"Error retrieving jobs for user {current_user.username}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve crawl jobs.")

@customer_router.post("/submit_crawl", response_model=Dict[str, str], status_code=status.HTTP_202_ACCEPTED)
async def submit_customer_crawl_job(request: QueueCrawlRequest, current_user: User = Depends(get_current_user)):
    """
    Submits a new crawl job for the authenticated customer.
    """
    logger.info(f"Customer user {current_user.username} submitting new crawl job for {request.target_url}.")
    
    # In a real system, you'd check customer's remaining crawl credits/quota here
    # For now, we'll allow submission.
    
    # Override job_type if not provided in config, or ensure it's a customer-allowed type
    if request.config is None:
        request.config = CrawlConfigRequest().model_dump() # Use default config if none provided
    if 'job_type' not in request.config or not request.config['job_type']:
        request.config['job_type'] = 'customer_initiated_crawl' # Default job type for customer submissions

    try:
        # The submit_crawl_to_queue function expects a QueueCrawlRequest
        response = await submit_crawl_to_queue(request)
        return response
    except Exception as e:
        logger.error(f"Error submitting crawl job for user {current_user.username}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to submit crawl job: {e}")

@customer_router.get("/usage", response_model=Dict[str, Any])
async def get_customer_usage_metrics(current_user: User = Depends(get_current_user)):
    """
    Retrieve usage metrics for the authenticated customer.
    """
    logger.info(f"Customer user {current_user.username} requesting usage metrics.")
    
    # This is a placeholder. In a real system, you'd query a dedicated usage tracking system
    # or aggregate from job/API logs associated with the user's ID.
    
    # Simulate usage data
    simulated_usage = {
        "api_calls_this_month": 15000,
        "api_calls_limit": 20000,
        "crawl_credits_used": 500,
        "crawl_credits_total": 1000,
        "reports_generated_this_month": 5,
        "last_updated": datetime.utcnow().isoformat()
    }
    
    return simulated_usage

