import logging
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Response, Query
from fastapi.security import OAuth2PasswordRequestForm
from datetime import datetime, timedelta # Import datetime and timedelta
import json # Import json

from Link_Profiler.core.models import User, CrawlStatus
from Link_Profiler.api.schemas import UserCreate, UserResponse, SystemConfigResponse, SystemConfigUpdate, Token
from Link_Profiler.api.dependencies import get_current_admin_user, get_current_user
from Link_Profiler.database.database import db
from Link_Profiler.services.auth_service import auth_service_instance
from Link_Profiler.config.config_loader import config_loader
from Link_Profiler.utils.logging_config import LoggingConfig # For re-applying logging config
from Link_Profiler.api.monitoring_debug import health_check_internal, _get_aggregated_stats_for_api, _get_satellites_data_internal # Import monitoring debug functions
from Link_Profiler.queue_system.job_coordinator import get_coordinator # Import canonical get_coordinator

logger = logging.getLogger(__name__)

admin_router = APIRouter(prefix="/admin", tags=["Admin"])

@admin_router.get("/users", response_model=List[UserResponse])
async def get_all_users(current_user: User = Depends(get_current_admin_user)):
    """Retrieve all users. Requires admin access."""
    logger.info(f"Admin user {current_user.username} requesting all users.")
    users = db.get_all_users()
    return [UserResponse.from_user(user) for user in users]

@admin_router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_new_user(user_create: UserCreate, current_user: User = Depends(get_current_admin_user)):
    """Create a new user. Requires admin access."""
    logger.info(f"Admin user {current_user.username} creating new user: {user_create.username}.")
    existing_user = db.get_user_by_username(user_create.username)
    if existing_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already registered")
    existing_email = db.get_user_by_email(user_create.email)
    if existing_email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")
    
    new_user = await auth_service_instance.register_user(
        username=user_create.username,
        email=user_create.email,
        password=user_create.password,
        is_admin=user_create.is_admin # Allow admin to set admin status
    )
    return UserResponse.from_user(new_user)

@admin_router.put("/users/{user_id}", response_model=UserResponse)
async def update_existing_user(user_id: str, user_update: UserCreate, current_user: User = Depends(get_current_admin_user)):
    """Update an existing user's details. Requires admin access."""
    logger.info(f"Admin user {current_user.username} updating user ID: {user_id}.")
    user = db.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    # Update fields
    user.username = user_update.username
    user.email = user_update.email
    user.is_admin = user_update.is_admin
    
    # Handle password change if provided
    if user_update.password:
        user.hashed_password = auth_service_instance.get_password_hash(user_update.password)
    
    updated_user = db.update_user(user)
    return UserResponse.from_user(updated_user)

@admin_router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_existing_user(user_id: str, current_user: User = Depends(get_current_admin_user)):
    """Delete a user. Requires admin access."""
    logger.info(f"Admin user {current_user.username} deleting user ID: {user_id}.")
    if current_user.id == user_id: # Use current_user.id instead of current_user.user_id
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete your own account.")
    
    success = db.delete_user(user_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)

@admin_router.get("/config", response_model=SystemConfigResponse)
async def get_system_config(current_user: User = Depends(get_current_admin_user)):
    """Retrieve current system configuration. Requires admin access."""
    logger.info(f"Admin user {current_user.username} requesting system config.")
    # For simplicity, return a subset of config that might be editable via UI
    # In a real app, you'd have a dedicated config service/model
    return SystemConfigResponse(
        logging_level=config_loader.get("logging.level"),
        api_cache_enabled=config_loader.get("api_cache.enabled"),
        api_cache_ttl=config_loader.get("api_cache.ttl"),
        crawler_max_depth=config_loader.get("crawler.max_depth"),
        crawler_render_javascript=config_loader.get("crawler.render_javascript"),
        # Add other relevant config items here
    )

@admin_router.put("/config", response_model=SystemConfigResponse)
async def update_system_config(config_update: SystemConfigUpdate, current_user: User = Depends(get_current_admin_user)):
    """Update system configuration. Requires admin access."""
    logger.info(f"Admin user {current_user.username} updating system config.")
    # Apply updates to config_loader (which should persist them if configured)
    if config_update.logging_level:
        config_loader.set("logging.level", config_update.logging_level)
        LoggingConfig.setup_logging(level=config_update.logging_level) # Re-apply logging config
    if config_update.api_cache_enabled is not None:
        config_loader.set("api_cache.enabled", config_update.api_cache_enabled)
    if config_update.api_cache_ttl is not None:
        config_loader.set("api_cache.ttl", config_update.api_cache_ttl)
    if config_update.crawler_max_depth is not None:
        config_loader.set("crawler.max_depth", config_update.crawler_max_depth)
    if config_update.crawler_render_javascript is not None:
        config_loader.set("crawler.render_javascript", config_update.crawler_render_javascript)
    
    # Reload config to ensure changes are reflected (if config_loader supports it)
    config_loader.reload_config() # Assuming this method exists and persists changes
    
    return SystemConfigResponse(
        logging_level=config_loader.get("logging.level"),
        api_cache_enabled=config_loader.get("api_cache.enabled"),
        api_cache_ttl=config_loader.get("api_cache.ttl"),
        crawler_max_depth=config_loader.get("crawler.max_depth"),
        crawler_render_javascript=config_loader.get("crawler.render_javascript"),
    )

@admin_router.get("/audit_logs", response_model=List[Dict[str, Any]])
async def get_audit_logs(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_admin_user)
):
    """Retrieve recent audit logs. Requires admin access."""
    logger.info(f"Admin user {current_user.username} requesting audit logs (limit={limit}, offset={offset}).")
    # This is a placeholder. In a real system, you'd query a dedicated audit log database/service.
    # For now, simulate some logs.
    simulated_logs = [
        {"timestamp": datetime.now().isoformat(), "user": "admin", "action": "LOGIN_SUCCESS", "details": {"ip": "192.168.1.1"}},
        {"timestamp": (datetime.now() - timedelta(minutes=5)).isoformat(), "user": "admin", "action": "UPDATE_CONFIG", "details": {"key": "logging.level", "old": "INFO", "new": "DEBUG"}},
        {"timestamp": (datetime.now() - timedelta(hours=1)).isoformat(), "user": "user1", "action": "SUBMIT_CRAWL_JOB", "details": {"job_id": "abc-123", "target": "example.com"}},
    ]
    return simulated_logs[offset:offset+limit]

@admin_router.post("/api_keys/{api_name}/update", response_model=Dict[str, str])
async def update_api_key(api_name: str, new_key: str, current_user: User = Depends(get_current_admin_user)):
    """Update an external API key. Requires admin access."""
    logger.info(f"Admin user {current_user.username} updating API key for {api_name}.")
    # This is a placeholder. You would update this in a secure config store.
    # For now, directly update config_loader (not persistent across restarts unless configured)
    current_config = config_loader.get("external_apis", {})
    if api_name in current_config:
        current_config[api_name]["api_key"] = new_key
        config_loader.set("external_apis", current_config) # This might not persist depending on config_loader impl
        config_loader.reload_config() # Attempt to persist/reload
        return {"message": f"API key for {api_name} updated successfully."}
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"API {api_name} not found in configuration.")

# --- Re-exposed Monitoring Endpoints from dashboard_server.py ---
# These endpoints are now part of the main API for Mission Control to consume.

@admin_router.get("/monitoring/health")
async def health_check_main_endpoint(current_user: User = Depends(get_current_admin_user)): # Added admin dependency
    """
    Performs a comprehensive health check of the API and its dependencies.
    Requires admin authentication.
    """
    logger.info(f"Admin user {current_user.username} requesting health check.")
    health_status = await health_check_internal()
    status_code = status.HTTP_200_OK if health_status["status"] == "healthy" else status.HTTP_503_SERVICE_UNAVAILABLE
    return Response(content=json.dumps(health_status, indent=2), media_type="application/json", status_code=status_code)

@admin_router.get("/monitoring/stats")
async def get_api_stats_main_endpoint(current_user: User = Depends(get_current_admin_user)):
    """
    Retrieves aggregated statistics for the Link Profiler system.
    Requires admin authentication.
    """
    logger.info(f"Admin user {current_user.username} requesting aggregated stats.")
    return await _get_aggregated_stats_for_api()

@admin_router.get("/monitoring/satellites")
async def get_satellites_main_endpoint(current_user: User = Depends(get_current_admin_user)):
    """
    Retrieves detailed health information for all satellite crawlers.
    Requires admin authentication.
    """
    logger.info(f"Admin user {current_user.username} requesting detailed satellite health.")
    return await _get_satellites_data_internal()

@admin_router.get("/monitoring/jobs")
async def get_jobs_main_endpoint(
    status_filter: Optional[str] = Query(None, description="Filter jobs by status (e.g., 'PENDING', 'IN_PROGRESS', 'COMPLETED', 'FAILED', 'CANCELLED')."),
    current_user: User = Depends(get_current_admin_user)
):
    """
    Retrieves a list of crawl jobs, optionally filtered by status.
    Requires admin authentication.
    """
    logger.info(f"Admin user {current_user.username} requesting jobs (status_filter: {status_filter}).")
    
    try:
        all_jobs = db.get_all_crawl_jobs()
        
        if status_filter:
            try:
                filter_status = CrawlStatus[status_filter.upper()]
                all_jobs = [job for job in all_jobs if job.status == filter_status]
            except KeyError:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid status_filter: {status_filter}. Must be one of {list(CrawlStatus.__members__.keys())}.")
        
        # Sort by created date, newest first
        sorted_jobs = sorted(all_jobs, key=lambda job: job.created_at, reverse=True)
        
        # Convert CrawlJob objects to their dictionary representation for JSON serialization
        return [job.to_dict() for job in sorted_jobs]
    except Exception as e:
        logger.error(f"Error retrieving jobs: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to retrieve jobs: {e}")
    finally:
        if db and hasattr(db, 'Session'):
            db.Session.remove()

@admin_router.post("/monitoring/jobs/{job_id}/cancel")
async def cancel_job_main_endpoint(job_id: str, current_user: User = Depends(get_current_admin_user)):
    """
    Cancels a specific crawl job.
    Requires admin authentication.
    """
    logger.info(f"Admin user {current_user.username} requesting to cancel job {job_id}.")
    try:
        coordinator = await get_coordinator()
        success = await coordinator.cancel_job(job_id)
        if success:
            return {"message": f"Job {job_id} cancelled successfully."}
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Job {job_id} not found or could not be cancelled.")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling job {job_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to cancel job {job_id}: {e}")

@admin_router.post("/monitoring/jobs/pause_all")
async def pause_all_jobs_main_endpoint(current_user: User = Depends(get_current_admin_user)):
    """
    Pauses all new job processing.
    Requires admin authentication.
    """
    logger.info(f"Admin user {current_user.username} requesting to pause all jobs.")
    try:
        coordinator = await get_coordinator()
        await coordinator.pause_job_processing()
        return {"message": "All new job processing paused."}
    except Exception as e:
        logger.error(f"Error pausing all jobs: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to pause all jobs: {e}")

@admin_router.post("/monitoring/jobs/resume_all")
async def resume_all_jobs_main_endpoint(current_user: User = Depends(get_current_admin_user)):
    """
    Resumes all job processing.
    Requires admin authentication.
    """
    logger.info(f"Admin user {current_user.username} requesting to resume all jobs.")
    try:
        coordinator = await get_coordinator()
        await coordinator.resume_job_processing()
        return {"message": "All job processing resumed."}
    except Exception as e:
        logger.error(f"Error resuming all jobs: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to resume all jobs: {e}")

@admin_router.post("/monitoring/satellites/control/{crawler_id}/{command}")
async def control_single_satellite_main_endpoint(crawler_id: str, command: str, current_user: User = Depends(get_current_admin_user)):
    """
    Sends a control command to a specific satellite crawler.
    Commands: PAUSE, RESUME, SHUTDOWN, RESTART.
    Requires admin authentication.
    """
    logger.info(f"Admin user {current_user.username} requesting command '{command}' for satellite '{crawler_id}'.")
    try:
        coordinator = await get_coordinator()
        response = await coordinator.send_control_command(crawler_id, command)
        return response
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error controlling satellite {crawler_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to control satellite {crawler_id}: {e}")

@admin_router.post("/monitoring/satellites/control/all/{command}")
async def control_all_satellites_main_endpoint(command: str, current_user: User = Depends(get_current_admin_user)):
    """
    Sends a control command to all active satellite crawlers.
    Commands: PAUSE, RESUME, SHUTDOWN, RESTART.
    Requires admin authentication.
    """
    logger.info(f"Admin user {current_user.username} requesting command '{command}' for all satellites.")
    try:
        coordinator = await get_coordinator()
        response = await coordinator.send_global_control_command(command)
        return response
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error controlling all satellites: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to control all satellites: {e}")

# --- Debugging Endpoint for User Info ---
@admin_router.get("/debug/user_info/{username}", response_model=UserResponse)
async def debug_user_info(username: str, current_user: User = Depends(get_current_admin_user)):
    """
    DEBUG endpoint: Retrieve detailed info for a specific user. Requires admin access.
    """
    logger.info(f"Admin user {current_user.username} requesting debug info for user: {username}.")
    user = db.get_user_by_username(username)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    return UserResponse.from_user(user)
