"""
Central Job Coordinator - Distributes crawl jobs to satellite crawlers
"""
import asyncio
import redis.asyncio as redis
import json
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from dataclasses import asdict
import logging
from croniter import croniter
import aiohttp
import os

from Link_Profiler.core.models import CrawlJob, CrawlConfig, CrawlStatus, serialize_model, CrawlError
from Link_Profiler.database.database import Database
from Link_Profiler.config.config_loader import ConfigLoader # Import ConfigLoader
from Link_Profiler.services.alert_service import AlertService
from Link_Profiler.utils.connection_manager import ConnectionManager

# Initialize and load config once using the absolute path
# Assuming this file is at Link_Profiler/queue_system/job_coordinator.py
# The project root is two levels up.
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
config_loader = ConfigLoader()
config_loader.load_config(config_dir=os.path.join(project_root, "Link_Profiler", "config"), env_var_prefix="LP_")

logger = logging.getLogger(__name__)

class JobCoordinator:
    """Manages distributed crawling jobs via Redis queues"""
    
    def __init__(self, redis_url: str = None, database: Database = None, alert_service: Optional[AlertService] = None, connection_manager: Optional[ConnectionManager] = None):
        # Load Redis URL from config_loader, with fallback to environment variable then hardcoded default
        redis_url = redis_url or config_loader.get("redis.url", os.getenv("REDIS_URL", "redis://:redis_secure_pass_456@127.0.0.1:6379/0"))
        self.redis_pool = redis.ConnectionPool.from_url(redis_url)
        self.redis = redis.Redis(connection_pool=self.redis_pool)
        self.db = database
        self.alert_service = alert_service
        self.connection_manager = connection_manager
        
        # Queue names
        self.job_queue = config_loader.get("queue.job_queue_name", "crawl_jobs")
        self.result_queue = config_loader.get("queue.result_queue_name", "crawl_results")
        self.heartbeat_queue_sorted = config_loader.get("queue.heartbeat_queue_sorted_name", "crawler_heartbeats_sorted") # Modified: Load from config
        self.scheduled_jobs_queue = config_loader.get("queue.scheduled_jobs_queue", "scheduled_jobs") # New: Scheduled jobs queue name
        
        # Job tracking (authoritative state is in DB, this is for quick in-memory lookup of active jobs)
        self.active_jobs_cache: Dict[str, CrawlJob] = {}
        # Changed satellite_crawlers to store the full heartbeat data, not just last_seen time
        self.satellite_crawlers: Dict[str, Dict[str, Any]] = {} 
        
        self.scheduler_interval = config_loader.get("queue.scheduler_interval", 5)
        self.stale_timeout = config_loader.get("queue.stale_timeout", 60) # Added stale_timeout from config

        # New: Current desired code version for satellites and version control flag
        self.current_code_version = config_loader.get("system.current_code_version", "unknown")
        self.version_control_enabled = config_loader.get("system.version_control_enabled", False) # New: Load version control flag
        logger.info(f"JobCoordinator: Desired satellite code version: {self.current_code_version}")
        logger.info(f"JobCoordinator: Version control enabled: {self.version_control_enabled}")

        # Webhook configuration (for job completion webhooks)
        self.webhook_enabled = config_loader.get("notifications.webhooks.enabled", False)
        self.webhook_urls = config_loader.get("notifications.webhooks.urls", [])
        self._session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        # Ensure Redis connection is active
        try:
            await self.redis.ping()
            logger.info("JobCoordinator connected to Redis successfully.")
        except Exception as e:
            logger.error(f"JobCoordinator failed to connect to Redis: {e}", exc_info=True)
            raise
        
        # New: Initialize aiohttp client session
        if self.webhook_enabled and not self._session:
            self._session = aiohttp.ClientSession()
            logger.info("JobCoordinator aiohttp client session created for webhooks.")
        
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.redis.close()
        logger.info("JobCoordinator Redis connection closed.")
        
        # New: Close aiohttp client session
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
            logger.info("JobCoordinator aiohttp client session closed.")
    
    async def submit_crawl_job(self, job: CrawlJob) -> str:
        """Submit a new crawl job to the queue (either immediate or scheduled)"""
        
        # Add job to database first (authoritative source)
        self.db.add_crawl_job(job)
        
        job_message = serialize_model(job)

        if job.scheduled_at:
            # If job.scheduled_at is in the past, treat as immediate
            if job.scheduled_at <= datetime.now():
                logger.info(f"Scheduled job {job.id} is due now. Adding to immediate queue.")
                await self.redis.zadd(self.job_queue, {json.dumps(job_message): job.priority})
            else:
                # Add to scheduled jobs queue with scheduled_at timestamp as score
                await self.redis.zadd(self.scheduled_jobs_queue, {json.dumps(job_message): job.scheduled_at.timestamp()})
                logger.info(f"Scheduled job {job.id} (type: {job.job_type}) for {job.target_url} scheduled at {job.scheduled_at} with cron '{job.cron_schedule}'.")
        else:
            # Add to immediate queue with priority
            await self.redis.zadd(self.job_queue, {json.dumps(job_message): job.priority})
            logger.info(f"Submitted immediate crawl job {job.id} (type: {job.job_type}) for {job.target_url} with priority {job.priority}")
        
        # Add to in-memory cache for quick lookup by get_job_status
        self.active_jobs_cache[job.id] = job

        # New: Broadcast job submission to WebSocket clients
        if self.connection_manager:
            await self.connection_manager.broadcast({
                "type": "job_submitted",
                "job_id": job.id,
                "job_type": job.job_type,
                "target_url": job.target_url,
                "status": job.status.value,
                "created_date": job.created_date.isoformat()
            })
        
        return job.id
    
    async def get_job_status(self, job_id: str) -> Optional[CrawlJob]:
        """Get current status of a crawl job from the database."""
        # Query the database for the authoritative status
        job = self.db.get_crawl_job(job_id)
        if job:
            # Update cache if found in DB
            self.active_jobs_cache[job_id] = job
        return job
    
    async def process_results(self):
        """Process results from satellite crawlers"""
        logger.info("Starting result processing loop.")
        while True:
            try:
                # Pop result from queue (blocking with timeout)
                result = await self.redis.blpop(self.result_queue, timeout=1)
                
                if result:
                    _, result_data = result
                    result_json = json.loads(result_data)
                    
                    job_id = result_json.get("job_id")
                    # Fetch job from DB to ensure we have the latest authoritative state
                    job = self.db.get_crawl_job(job_id)
                    
                    if job:
                        await self._update_job_progress(job, result_json)
                        # Update in-memory cache after DB update
                        self.active_jobs_cache[job_id] = job
                    else:
                        logger.warning(f"Received result for unknown or deleted job ID: {job_id}. Data: {result_json}")
                
            except Exception as e:
                logger.error(f"Error processing results: {e}", exc_info=True)
                await asyncio.sleep(1)
    
    async def _update_job_progress(self, job: CrawlJob, result_data: Dict):
        """Update job progress from satellite results and persist to DB"""
        
        # Update job metrics
        job.urls_crawled = result_data.get("urls_crawled", job.urls_crawled)
        job.links_found = result_data.get("links_found", job.links_found)
        job.progress_percentage = min(100.0, result_data.get("progress_percentage", job.progress_percentage))
        
        # Handle job status updates
        status_str = result_data.get("status")
        if status_str:
            job.status = CrawlStatus(status_str) # Convert string back to Enum
        
        if job.status == CrawlStatus.COMPLETED:
            job.completed_date = datetime.now()
            job.results = result_data.get("results", {})
            logger.info(f"Job {job.id} completed successfully")

            # If it's a recurring job, schedule the next run
            if job.cron_schedule:
                try:
                    iter = croniter(job.completed_date, job.cron_schedule) # croniter expects date first, then cron string
                    next_run_time = iter.get_next(datetime)
                    
                    # Create a new job instance for the next run
                    next_job = CrawlJob(
                        id=str(uuid.uuid4()),
                        target_url=job.target_url,
                        job_type=job.job_type,
                        status=CrawlStatus.PENDING,
                        priority=job.priority,
                        created_date=datetime.now(),
                        scheduled_at=next_run_time,
                        cron_schedule=job.cron_schedule,
                        config=job.config # Copy original config
                    )
                    self.db.add_crawl_job(next_job) # Add to DB
                    await self.redis.zadd(self.scheduled_jobs_queue, {json.dumps(serialize_model(next_job)): next_run_time.timestamp()})
                    logger.info(f"Recurring job {job.id} completed. Next run ({next_job.id}) scheduled for {next_run_time}.")
                except Exception as e:
                    logger.error(f"Failed to schedule next run for recurring job {job.id}: {e}", exc_info=True)
                    job.add_error(url="N/A", error_type="SchedulingError", message=f"Failed to schedule next run: {str(e)}")
        
        elif job.status == CrawlStatus.FAILED:
            job.completed_date = datetime.now()
            error_message = result_data.get("error_message", "Unknown error")
            failed_url = result_data.get("failed_url", "N/A")
            error_log_data = result_data.get("error_log", [])
            
            # Reconstruct error_log if provided by satellite
            if error_log_data:
                job.error_log = [CrawlError.from_dict(err_data) for err_data in error_log_data]
                job.errors_count = len(job.error_log)
            else:
                job.add_error(url=failed_url, error_type="SatelliteFailure", message=error_message)
            
            logger.error(f"Job {job.id} failed: {error_message}")
        
        # Persist updated job state to DB
        self.db.update_crawl_job(job)

        # New: Send webhook notification if enabled and job is completed or failed
        if self.webhook_enabled and (job.status == CrawlStatus.COMPLETED or job.status == CrawlStatus.FAILED):
            await self._send_webhook_notification(job)

        # New: Evaluate alert rules for job status changes or anomalies
        if self.alert_service:
            await self.alert_service.evaluate_job_update(job)

        # New: Broadcast job update to WebSocket clients
        if self.connection_manager:
            await self.connection_manager.broadcast({
                "type": "job_update",
                "job_id": job.id,
                "job_type": job.job_type,
                "target_url": job.target_url,
                "status": job.status.value,
                "progress_percentage": job.progress_percentage,
                "urls_crawled": job.urls_crawled,
                "links_found": job.links_found,
                "errors_count": job.errors_count,
                "completed_date": job.completed_date.isoformat() if job.completed_date else None
            })
    
    async def _send_webhook_notification(self, job: CrawlJob):
        """Sends a webhook notification for a job status change."""
        if not self._session:
            logger.warning("Webhook session not initialized. Cannot send notification.")
            return

        payload = {
            "job_id": job.id,
            "target_url": job.target_url,
            "job_type": job.job_type,
            "status": job.status.value,
            "progress_percentage": job.progress_percentage,
            "completed_date": job.completed_date.isoformat() if job.completed_date else None,
            "errors_count": job.errors_count,
            "error_log_summary": [err.message for err in job.error_log] if job.error_log else [],
            "results_summary": job.results # Send full results for now, can be filtered later
        }

        for url in self.webhook_urls:
            try:
                async with self._session.post(url, json=payload, timeout=10) as response:
                    response.raise_for_status()
                    logger.info(f"Successfully sent webhook for job {job.id} to {url}. Status: {response.status}")
            except aiohttp.ClientError as e:
                logger.error(f"Failed to send webhook for job {job.id} to {url}: {e}", exc_info=True)
            except asyncio.TimeoutError:
                logger.warning(f"Webhook to {url} for job {job.id} timed out.")
            except Exception as e:
                logger.error(f"Unexpected error sending webhook for job {job.id} to {url}: {e}", exc_info=True)

    async def monitor_satellites(self):
        """Monitor satellite crawler health via heartbeats and trigger restarts for outdated versions."""
        logger.info("Starting satellite monitoring loop.")
        while True:
            try:
                # Get all crawler_ids and their last heartbeat timestamps from the sorted set
                # Only fetch those that are within the stale_timeout period
                cutoff = (datetime.now() - timedelta(seconds=self.stale_timeout)).timestamp()
                logger.debug(f"Monitor: Checking for active crawlers with heartbeat score >= {cutoff}") # Added log
                
                # Fetch members (crawler_ids) and their scores (timestamps)
                active_crawler_ids_with_timestamps = await self.redis.zrangebyscore(
                    self.heartbeat_queue_sorted, 
                    cutoff, 
                    "+inf", 
                    withscores=True
                )
                
                logger.debug(f"Monitor: Found {len(active_crawler_ids_with_timestamps)} potential active crawlers in sorted set.") # Added log
                if not active_crawler_ids_with_timestamps:
                    logger.debug("Monitor: No active crawlers found in sorted set within cutoff.") # Added log

                current_active_crawlers_details = {}
                for crawler_id_bytes, timestamp in active_crawler_ids_with_timestamps:
                    crawler_id = crawler_id_bytes.decode('utf-8')
                    logger.debug(f"Monitor: Processing crawler_id '{crawler_id}' from sorted set with timestamp {timestamp}") # Added log
                    
                    # Fetch the detailed heartbeat data for this crawler_id
                    detailed_heartbeat_json = await self.redis.get(f"crawler_details:{crawler_id}")
                    
                    if detailed_heartbeat_json:
                        try:
                            detailed_heartbeat_data = json.loads(detailed_heartbeat_json)
                            
                            # New: Check for code version mismatch ONLY if version control is enabled
                            if self.version_control_enabled:
                                satellite_code_version = detailed_heartbeat_data.get("code_version", "unknown")
                                logger.debug(f"Monitor: Comparing satellite '{crawler_id}' version '{satellite_code_version}' with desired '{self.current_code_version}'.") # New debug log
                                if satellite_code_version != self.current_code_version:
                                    logger.warning(f"Satellite '{crawler_id}' is outdated (version: {satellite_code_version}, desired: {self.current_code_version}). Sending RESTART command.")
                                    await self.send_control_command(crawler_id, "RESTART")
                                    detailed_heartbeat_data["is_outdated"] = True # Mark as outdated for dashboard
                                else:
                                    detailed_heartbeat_data["is_outdated"] = False # Mark as not outdated
                            else:
                                logger.debug(f"Monitor: Version control is disabled. Skipping version check for satellite '{crawler_id}'.")
                                detailed_heartbeat_data["is_outdated"] = False # Assume not outdated if feature is off
                                
                            current_active_crawlers_details[crawler_id] = detailed_heartbeat_data
                            logger.debug(f"Monitor: Successfully retrieved detailed data for '{crawler_id}': {detailed_heartbeat_data}") # Added log
                        except json.JSONDecodeError:
                            logger.warning(f"Monitor: Invalid detailed heartbeat data for {crawler_id}: {detailed_heartbeat_json}")
                    else:
                        logger.warning(f"Monitor: No detailed heartbeat data found for active crawler_id: {crawler_id}. It might have expired or not been set.") # Added log
                
                # Update internal state with the de-duplicated, detailed information
                self.satellite_crawlers = current_active_crawlers_details
                logger.info(f"Monitor: Currently tracking {len(self.satellite_crawlers)} active satellites.") # Added log
                
                # Clean up old heartbeats from Redis sorted set (optional, but good for memory)
                # This removes entries from the ZSET that are older than the cutoff
                await self.redis.zremrangebyscore(self.heartbeat_queue_sorted, 0, cutoff)
                
            except Exception as e:
                logger.error(f"Error monitoring satellites: {e}", exc_info=True)
            finally:
                await asyncio.sleep(10)
    
    async def _process_scheduled_jobs(self):
        """
        Periodically checks the scheduled jobs queue and moves due jobs
        to the main job queue.
        """
        logger.info("Starting scheduled jobs processing loop.")
        while True:
            try:
                now_timestamp = datetime.now().timestamp()
                
                # Get all jobs that are due (score <= current timestamp)
                due_jobs = await self.redis.zrangebyscore(
                    self.scheduled_jobs_queue, 
                    "-inf", 
                    now_timestamp, 
                    withscores=False
                )
                
                if due_jobs:
                    logger.info(f"Found {len(due_jobs)} scheduled jobs due for processing.")
                    for job_json in due_jobs:
                        job_dict = json.loads(job_json)
                        job = CrawlJob.from_dict(job_dict)
                        
                        # Remove from scheduled queue
                        await self.redis.zrem(self.scheduled_jobs_queue, job_json)
                        
                        # Add to main job queue
                        await self.redis.zadd(self.job_queue, {json.dumps(serialize_model(job)): job.priority})
                        logger.info(f"Moved scheduled job {job.id} (type: {job.job_type}) to main job queue.")
                        
                
            except Exception as e:
                logger.error(f"Error processing scheduled jobs: {e}", exc_info=True)
            finally:
                await asyncio.sleep(self.scheduler_interval)
    
    async def get_queue_stats(self) -> Dict:
        """
        Get current queue statistics and detailed satellite information.
        """
        pending_jobs = await self.redis.zcard(self.job_queue)
        scheduled_jobs = await self.redis.zcard(self.scheduled_jobs_queue)
        active_crawlers = len(self.satellite_crawlers)
        
        # Total and completed jobs should ideally come from DB for accuracy
        total_jobs_db = len(self.db.get_all_crawl_jobs())
        completed_jobs_db = len([j for j in self.db.get_all_crawl_jobs() if j.is_completed])
        
        return {
            "pending_jobs": pending_jobs,
            "scheduled_jobs": scheduled_jobs,
            "active_crawlers": active_crawlers,
            "total_jobs": total_jobs_db,
            "completed_jobs": completed_jobs_db,
            "satellite_crawlers": self.satellite_crawlers # Include the detailed satellite info
        }

    async def pause_job_processing(self) -> bool:
        """Pauses all new job processing by satellites."""
        try:
            await self.redis.set("processing_paused", "true", ex=3600) # Set for 1 hour
            logger.info("Global job processing paused.")
            return True
        except Exception as e:
            logger.error(f"Failed to pause global job processing: {e}", exc_info=True)
            return False

    async def resume_job_processing(self) -> bool:
        """Resumes all new job processing by satellites."""
        try:
            await self.redis.delete("processing_paused")
            logger.info("Global job processing resumed.")
            return True
        except Exception as e:
            logger.error(f"Failed to resume global job processing: {e}", exc_info=True)
            return False

    async def cancel_job(self, job_id: str) -> bool:
        """
        Cancels a job. If running, attempts to signal cancellation.
        If pending/scheduled, removes from Redis queues.
        Updates job status in DB to CANCELLED.
        """
        job = self.db.get_crawl_job(job_id)
        if not job:
            logger.warning(f"Attempted to cancel non-existent job: {job_id}")
            return False

        if job.status in [CrawlStatus.COMPLETED, CrawlStatus.FAILED, CrawlStatus.CANCELLED]:
            logger.info(f"Job {job_id} is already in a final state ({job.status.value}). Cannot cancel.")
            return False

        # 1. Update DB status
        job.status = CrawlStatus.CANCELLED
        job.completed_date = datetime.now()
        job.add_error(url=job.target_url, error_type="ManualCancellation", message="Job cancelled by user/system.")
        self.db.update_crawl_job(job)
        logger.info(f"Job {job.id} status updated to CANCELLED in DB.")

        # 2. Remove from Redis queues if pending/scheduled
        job_message = json.dumps(serialize_model(job))
        removed_from_job_queue = await self.redis.zrem(self.job_queue, job_message)
        removed_from_scheduled_queue = await self.redis.zrem(self.scheduled_jobs_queue, job_message)
        
        if removed_from_job_queue or removed_from_scheduled_queue:
            logger.info(f"Job {job_id} removed from Redis queues (job_queue: {removed_from_job_queue}, scheduled_queue: {removed_from_scheduled_queue}).")
        else:
            logger.info(f"Job {job_id} was not found in Redis job/scheduled queues (might be in progress on a satellite).")

        # 3. Signal running satellite (if applicable) - this is more complex
        # For now, rely on the satellite's heartbeat mechanism to eventually pick up the cancelled status from DB
        # A more advanced solution would involve a dedicated Redis channel for control signals.
        
        # Remove from in-memory cache
        self.active_jobs_cache.pop(job_id, None)

        return True

    async def send_control_command(self, crawler_id: str, command: str) -> bool:
        """Sends a control command to a specific satellite crawler."""
        control_key = f"crawler_control:{crawler_id}"
        command_data = {"command": command, "timestamp": datetime.now().isoformat()}
        try:
            await self.redis.set(control_key, json.dumps(command_data), ex=self.stale_timeout * 3) # Command expires after a while
            logger.info(f"Sent command '{command}' to satellite '{crawler_id}'.")
            return True
        except Exception as e:
            logger.error(f"Failed to send command '{command}' to satellite '{crawler_id}': {e}", exc_info=True)
            return False

    async def send_global_control_command(self, command: str) -> bool:
        """Sends a control command to all active satellite crawlers."""
        control_key_all = "crawler_control:all"
        command_data = {"command": command, "timestamp": datetime.now().isoformat()}
        try:
            await self.redis.set(control_key_all, json.dumps(command_data), ex=self.stale_timeout * 3) # Command expires after a while
            logger.info(f"Sent global command '{command}' to all satellites.")
            return True
        except Exception as e:
            logger.error(f"Failed to send global command '{command}': {e}", exc_info=True)
            return False

    async def get_all_jobs_for_dashboard(self, status_filter: Optional[str] = None) -> List[CrawlJob]:
        """
        Retrieves all crawl jobs from the database, optionally filtered by status,
        for display on the dashboard.
        """
        if not self.db:
            logger.error("Database not connected, cannot retrieve jobs for dashboard.")
            return []
        try:
            all_jobs = self.db.get_all_crawl_jobs()
            
            if status_filter:
                try:
                    filter_status = CrawlStatus(status_filter.upper())
                    filtered_jobs = [job for job in all_jobs if job.status == filter_status]
                except ValueError:
                    logger.warning(f"Invalid status filter '{status_filter}'. Returning all jobs.")
                    filtered_jobs = all_jobs
            else:
                filtered_jobs = all_jobs
            
            # Sort by created date, newest first
            sorted_jobs = sorted(filtered_jobs, key=lambda job: job.created_date, reverse=True)
            return sorted_jobs
        except Exception as e:
            logger.error(f"Error retrieving all jobs for dashboard: {e}", exc_info=True)
            return []
        finally:
            if self.db and hasattr(self.db, 'Session'):
                self.db.Session.remove()

# Usage example (for running coordinator as a standalone process)
async def main():
    logging.basicConfig(level=logging.INFO)
    # Initialize Database for standalone coordinator if needed
    # Load DATABASE_URL from config_loader, with fallback to environment variable then hardcoded default
    DATABASE_URL = config_loader.get("database.url", os.getenv('DATABASE_URL', 'postgresql://linkprofiler:secure_password_123@localhost:5432/link_profiler_db'))
    db_instance = Database(db_url=DATABASE_URL) 
    alert_service_instance = AlertService(db_instance)
    # For standalone, connection_manager would be None or a dummy
    async with JobCoordinator(database=db_instance, alert_service=alert_service_instance, connection_manager=None) as coordinator:
        # Start monitoring tasks
        asyncio.create_task(coordinator.process_results())
        asyncio.create_task(coordinator.monitor_satellites())
        asyncio.create_task(coordinator._process_scheduled_jobs())
        asyncio.create_task(alert_service_instance.refresh_rules())
        
        logger.info("Job Coordinator started. Press Ctrl+C to exit.")
        # Keep the main task alive
        while True:
            await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
