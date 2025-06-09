"""
Job Coordinator - Manages distributed crawling jobs via Redis queues.
File: Link_Profiler/queue_system/job_coordinator.py
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
import uuid

import redis.asyncio as redis
from croniter import croniter

from Link_Profiler.config.config_loader import ConfigLoader
from Link_Profiler.database.database import Database
from Link_Profiler.services.alert_service import AlertService
from Link_Profiler.utils.connection_manager import ConnectionManager
from Link_Profiler.core.models import CrawlJob, CrawlStatus, serialize_model, CrawlError

logger = logging.getLogger(__name__)

class JobCoordinator:
    """
    Manages distributed crawling jobs via Redis queues.
    Handles job submission, status tracking, result processing,
    and coordination with satellite crawlers.
    """
    _instance = None

    # Corrected __new__ signature to accept *args and **kwargs
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(JobCoordinator, cls).__new__(cls)
            # _initialized flag should be set in __init__ to ensure it's only set once
            # even if __new__ is called multiple times (e.g., by get_coordinator)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, redis_client: redis.Redis, config_loader: ConfigLoader, database: Database,
                 alert_service: AlertService, connection_manager: ConnectionManager):
        if self._initialized:
            return
        self._initialized = True
        self.logger = logging.getLogger(__name__ + ".JobCoordinator")
        self.redis = redis_client
        self.config_loader = config_loader
        self.db = database
        self.alert_service = alert_service
        self.connection_manager = connection_manager # For WebSocket notifications

        self.job_queue_name = self.config_loader.get("queue.job_queue_name", "crawl_jobs")
        self.result_queue_name = self.config_loader.get("queue.result_queue_name", "crawl_results")
        self.dead_letter_queue_name = self.config_loader.get("queue.dead_letter_queue_name",
                                                              "dead_letter_queue")
        self.scheduled_jobs_queue_name = self.config_loader.get("queue.scheduled_jobs_queue",
                                                                 "scheduled_crawl_jobs")
        self.heartbeat_queue_name = self.config_loader.get("queue.heartbeat_queue_sorted_name",
                                                            "crawler_heartbeats_sorted")
        self.scheduler_interval = self.config_loader.get("queue.scheduler_interval", 5) # How often to check for scheduled jobs
        self.crawler_timeout = self.config_loader.get("monitoring.crawler_timeout", 30) # Seconds without heartbeat before considering crawler dead

        self._processing_paused = False
        self._processing_lock = asyncio.Lock()
        self._coordinator_running = False

        self.logger.info("JobCoordinator initialized.")

    async def __aenter__(self):
        """Starts background tasks for the coordinator."""
        if not self._coordinator_running:
            self._coordinator_running = True
            self.logger.info("JobCoordinator entering async context.")
            # These tasks are now started by get_coordinator() in main.py
            # asyncio.create_task(self.process_results())
            # asyncio.create_task(self.monitor_satellites())
            # asyncio.create_task(self._process_scheduled_jobs())
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Cleans up background tasks."""
        self._coordinator_running = False
        self.logger.info("JobCoordinator exiting async context.")
        # No need to explicitly cancel tasks here, as they should check _coordinator_running
        # and exit gracefully. Or, manage tasks explicitly if more robust shutdown is needed.

    async def submit_crawl_job(self, job: CrawlJob) -> str:
        """
        Submits a crawl job to the appropriate Redis queue.
        If scheduled, adds to scheduled queue. Otherwise, adds to main job queue.
        """
        job_data = serialize_model(job)
        job_json = json.dumps(job_data)

        if job.scheduled_at:
            # Store in a sorted set with timestamp as score
            await self.redis.zadd(self.scheduled_jobs_queue_name, {job_json: job.scheduled_at.timestamp()})
            job.status = CrawlStatus.PENDING # Ensure status is pending for scheduled jobs
            self.db.add_crawl_job(job) # Save to DB immediately
            self.logger.info(f"Scheduled job {job.id} for {job.scheduled_at}.")
        else:
            # Add to the main job queue
            await self.redis.lpush(self.job_queue_name, job_json)
            job.status = CrawlStatus.QUEUED # New status for jobs in Redis queue
            self.db.add_crawl_job(job) # Save to DB immediately
            self.logger.info(f"Submitted job {job.id} to queue.")

        # Notify via WebSocket
        await self.connection_manager.broadcast(f"Job {job.id} submitted. Status: {job.status.value}")
        await self.alert_service.evaluate_job_update(job) # Evaluate for alerts
        return job.id

    async def get_job_status(self, job_id: str) -> Optional[CrawlJob]:
        """Retrieves the current status of a job from the database."""
        job = self.db.get_crawl_job(job_id)
        if job:
            # If job is in PENDING/QUEUED state, check Redis for more up-to-date status
            if job.status in [CrawlStatus.PENDING, CrawlStatus.QUEUED]:
                # Note: lpos is O(N), might be slow for large queues. Consider alternative if performance is an issue.
                if await self.redis.lpos(self.job_queue_name, json.dumps(serialize_model(job))) is not None:
                    job.status = CrawlStatus.QUEUED
                # Check if it's in the scheduled queue
                elif await self.redis.zscore(self.scheduled_jobs_queue_name,
                                              json.dumps(serialize_model(job))) is not None:
                    job.status = CrawlStatus.PENDING # Still pending if in scheduled queue
                # If not found in Redis queues, but DB says PENDING/QUEUED, it might be picked up or lost.
                # For now, trust DB status if not found in Redis.

            # Check if it's currently being processed by a satellite
            # This would require a more complex mechanism, e.g., a hash map of active jobs
            # For now, rely on DB status for IN_PROGRESS.

            return job
        return None

    async def process_results(self):
        """
        Continuously monitors the result queue and processes completed job results.
        """
        self.logger.info("Starting result processing loop.")
        while self._coordinator_running:
            try:
                # Blocking pop from the result queue
                # timeout=0 means block indefinitely until an item is available
                result = await self.redis.brpop(self.result_queue_name, timeout=5)

                if result:
                    _, result_json = result
                    result_data = json.loads(result_json)

                    job_id = result_data.get("job_id")
                    # Fetch job from DB to ensure we have the latest authoritative state
                    job = self.db.get_crawl_job(job_id)

                    if job:
                        job.status = CrawlStatus(result_data.get("status")) # Update status from result
                        job.completed_date = datetime.now()
                        job.results = result_data.get("results", {})
                        job.urls_crawled = result_data.get("urls_crawled", job.urls_crawled)
                        job.links_found = result_data.get("links_found", job.links_found)
                        job.progress_percentage = result_data.get("progress_percentage",
                                                                   job.progress_percentage)

                        # Handle errors reported by crawler
                        crawler_errors = result_data.get("errors", [])
                        for err_data in crawler_errors:
                            job.add_error(
                                url=err_data.get("url", "N/A"),
                                error_type=err_data.get("error_type", "unknown"),
                                message=err_data.get("message", "No message"),
                                details=err_data.get("details")
                            )

                        self.db.update_crawl_job(job)
                        self.logger.info(f"Processed results for job {job_id}. Status: {job.status.value}")
                        await self.connection_manager.broadcast(f"Job {job.id} finished. Status: {job.status.value}")
                        await self.alert_service.evaluate_job_update(job) # Evaluate for alerts
                    else:
                        self.logger.warning(f"Received results for unknown job {job_id}. Moving to dead letter queue.")
                        await self.redis.lpush(self.dead_letter_queue_name, result_json)

            except redis.exceptions.ConnectionError as e:
                self.logger.error(f"Redis Connection Error in process_results: {e}. Attempting to reconnect in 5 seconds...", exc_info=True)
                # Wait a bit longer before retrying after a connection error
                await asyncio.sleep(5)
            except Exception as e:
                self.logger.error(f"Error processing results: {e}", exc_info=True)
                # Optionally, push malformed results to dead letter queue
                if 'result_json' in locals():
                    await self.redis.lpush(self.dead_letter_queue_name, result_json)
                await asyncio.sleep(1) # Prevent tight loop on persistent errors

    async def monitor_satellites(self):
        """
        Monitors satellite crawler heartbeats and identifies inactive crawlers.
        """
        self.logger.info("Starting satellite monitoring loop.")
        while self._coordinator_running:
            try:
                # Get all active crawlers (those that sent a heartbeat recently)
                min_score = (datetime.now() - timedelta(seconds=self.crawler_timeout)).timestamp()
                active_crawlers = await self.redis.zrangebyscore(self.heartbeat_queue_name, min_score,
                                                                 '+inf', withscores=True)

                current_active_ids = {crawler_id.decode('utf-8') for crawler_id, _ in active_crawlers}

                # Optionally, check for crawlers that were active but are now missing
                # This would require storing a list of previously active crawlers.
                # For simplicity, we'll just report current active ones.

                self.logger.debug(f"Active crawlers: {current_active_ids}")

                # Update Prometheus metrics for active crawlers
                # This would require a Gauge metric for active crawlers, updated here.
                # For now, just logging.

            except Exception as e:
                self.logger.error(f"Error monitoring satellites: {e}", exc_info=True)

            await asyncio.sleep(self.scheduler_interval) # Check every few seconds

    async def _process_scheduled_jobs(self):
        """
        Continuously checks the scheduled jobs queue and moves ready jobs to the main queue.
        """
        self.logger.info("Starting scheduled jobs processing loop.")
        while self._coordinator_running:
            try:
                now = datetime.now().timestamp()
                # Get all jobs whose scheduled_at is in the past or now
                ready_jobs = await self.redis.zrangebyscore(self.scheduled_jobs_queue_name, '-inf', now,
                                                             withscores=False)

                if ready_jobs:
                    self.logger.info(f"Found {len(ready_jobs)} scheduled jobs ready for processing.")
                    for job_json in ready_jobs:
                        job_data = json.loads(job_json)
                        job_id = job_data.get("id")

                        # Atomically remove from scheduled queue and add to main queue
                        pipe = self.redis.pipeline()
                        pipe.zrem(self.scheduled_jobs_queue_name, job_json)
                        pipe.lpush(self.job_queue_name, job_json)
                        await pipe.execute()

                        # Update job status in DB
                        job = self.db.get_crawl_job(job_id)
                        if job:
                            job.status = CrawlStatus.QUEUED
                            self.db.update_crawl_job(job)
                            self.logger.info(f"Moved scheduled job {job_id} to main queue.")
                            await self.connection_manager.broadcast(f"Scheduled job {job.id} moved to queue.")
                            await self.alert_service.evaluate_job_update(job) # Evaluate for alerts
                        else:
                            self.logger.warning(f"Scheduled job {job_id} found in Redis but not in DB.")

            except Exception as e:
                self.logger.error(f"Error processing scheduled jobs: {e}", exc_info=True)

            await asyncio.sleep(self.scheduler_interval)

    async def get_queue_stats(self) -> Dict:
        """
        Returns statistics about the job queues and active crawlers.
        """
        pending_jobs_count = await self.redis.llen(self.job_queue_name)
        results_pending_count = await self.redis.llen(self.result_queue_name)
        scheduled_jobs_count = await self.redis.zcard(self.scheduled_jobs_queue_name)

        # Get active crawlers and their last heartbeat
        min_score = (datetime.now() - timedelta(seconds=self.crawler_timeout)).timestamp()
        active_crawlers_raw = await self.redis.zrangebyscore(self.heartbeat_queue_name, min_score,
                                                                 '+inf', withscores=True)

        active_crawlers_info = {}
        for crawler_id_bytes, timestamp_float in active_crawlers_raw:
            crawler_id = crawler_id_bytes.decode('utf-8')
            active_crawlers_info[crawler_id] = {
                "last_seen": datetime.fromtimestamp(timestamp_float).isoformat(),
                "status": "active" # More detailed status would require more data in heartbeat
            }

        return {
            "pending_jobs": pending_jobs_count,
            "results_pending": results_pending_count,
            "scheduled_jobs": scheduled_jobs_count,
            "active_crawlers": len(active_crawlers_info),
            "satellite_crawlers": active_crawlers_info,
            "processing_paused": self._processing_paused,
            "timestamp": datetime.now().isoformat()
        }

    async def pause_job_processing(self) -> bool:
        """Pauses job processing by setting a flag."""
        async with self._processing_lock:
            self._processing_paused = True
            self.logger.info("Job processing paused.")
            await self.redis.set("job_processing_paused", "true") # Persist state
            # Broadcast pause command to all satellite crawlers so they halt new work
            await self.send_global_control_command("PAUSE")
            await self.connection_manager.broadcast("Job processing paused.")
            return True

    async def resume_job_processing(self) -> bool:
        """Resumes job processing by clearing the flag."""
        async with self._processing_lock:
            self._processing_paused = False
            self.logger.info("Job processing resumed.")
            await self.redis.delete("job_processing_paused") # Clear persisted state
            # Notify satellites to resume processing
            await self.send_global_control_command("RESUME")
            await self.connection_manager.broadcast("Job processing resumed.")
            return True

    async def is_processing_paused(self) -> bool:
        """Checks if job processing is currently paused."""
        paused_state = await self.redis.get("job_processing_paused")
        return paused_state is not None and paused_state.decode('utf-8').lower() == 'true'

    async def cancel_job(self, job_id: str) -> bool:
        """
        Cancels a job by removing it from queues and updating its status in DB.
        Also sends a control command to crawlers if job is in progress.
        """
        job = self.db.get_crawl_job(job_id)
        if not job:
            self.logger.warning(f"Attempted to cancel non-existent job {job_id}.")
            return False

        # Remove from job queue
        job_json = json.dumps(serialize_model(job))
        removed_count = await self.redis.lrem(self.job_queue_name, 0, job_json)
        if removed_count > 0:
            self.logger.info(f"Removed job {job_id} from job queue.")

        # Remove from scheduled queue
        removed_count += await self.redis.zrem(self.scheduled_jobs_queue_name, job_json)
        if removed_count > 0:
            self.logger.info(f"Removed job {job_id} from scheduled queue.")

        # Update DB status
        job.status = CrawlStatus.CANCELLED
        job.completed_date = datetime.now()
        self.db.update_crawl_job(job)
        self.logger.info(f"Job {job_id} cancelled and status updated in DB.")
        await self.connection_manager.broadcast(f"Job {job.id} cancelled.")
        await self.alert_service.evaluate_job_update(job) # Evaluate for alerts

        # If job might be currently processed by a crawler, broadcast a cancel command.
        # We may not know the exact crawler handling the job, so send a global
        # cancellation message. Crawlers listening on the Pub/Sub channel will
        # check the payload and stop if they are working on this job.
        await self.send_global_control_command("CANCEL_JOB", {"job_id": job_id})
        self.logger.info(
            f"Cancellation command broadcast for job {job_id}. Crawlers will stop if processing.")

        return True

    async def send_control_command(self, crawler_id: str, command: str, payload: Optional[Dict] = None) -> bool:
        """
        Sends a control command to a specific satellite crawler via Redis Pub/Sub.
        """
        channel = f"crawler_control:{crawler_id}"
        message = {"command": command, "payload": payload or {}}
        try:
            await self.redis.publish(channel, json.dumps(message))
            self.logger.info(f"Sent command '{command}' to crawler '{crawler_id}'.")
            return True
        except Exception as e:
            self.logger.error(f"Failed to send command to crawler '{crawler_id}': {e}", exc_info=True)
            return False

    async def send_global_control_command(self, command: str, payload: Optional[Dict] = None) -> bool:
        """
        Sends a control command to all connected satellite crawlers via Redis Pub/Sub.
        """
        channel = "crawler_control:all"
        message = {"command": command, "payload": payload or {}}
        try:
            await self.redis.publish(channel, json.dumps(message))
            self.logger.info(f"Sent global command '{command}' to all crawlers.")
            return True
        except Exception as e:
            self.logger.error(f"Failed to send global command: {e}", exc_info=True)
            return False


# Global coordinator instance
_job_coordinator_instance = None


async def get_coordinator() -> JobCoordinator: # Changed to async def
    """
    Get or create the global job coordinator instance.
    This function is responsible for initializing the JobCoordinator and starting its background tasks.
    Returns a simple mock coordinator if the full coordinator cannot be initialized.
    """
    global _job_coordinator_instance
    
    if _job_coordinator_instance is not None:
        return _job_coordinator_instance
    
    try:
        # Try to import and initialize the full coordinator
        from Link_Profiler.config.config_loader import config_loader
        from Link_Profiler.database.database import db
        from Link_Profiler.services.alert_service import alert_service_instance
        from Link_Profiler.utils.connection_manager import connection_manager
        import redis.asyncio as redis
        
        # Create Redis client
        redis_url = config_loader.get("redis.url")
        if redis_url:
            redis_client = redis.from_url(redis_url)
            _job_coordinator_instance = JobCoordinator(
                redis_client=redis_client,
                config_loader=config_loader,
                database=db,
                alert_service=alert_service_instance,
                connection_manager=connection_manager
            )
            logger.info("Full JobCoordinator instance created successfully.")
            # Start background tasks here, as this is the first time coordinator is accessed
            # This ensures tasks are started only once when the coordinator is first retrieved.
            asyncio.create_task(_job_coordinator_instance.process_results())
            asyncio.create_task(_job_coordinator_instance.monitor_satellites())
            asyncio.create_task(_job_coordinator_instance._process_scheduled_jobs())
            logger.info("JobCoordinator background tasks started.")
        else:
            logger.warning("Redis URL not configured, creating mock coordinator.")
            _job_coordinator_instance = _create_mock_coordinator()
            
    except Exception as e:
        logger.warning(f"Failed to create full JobCoordinator: {e}. Creating mock coordinator.")
        _job_coordinator_instance = _create_mock_coordinator()
    
    return _job_coordinator_instance


async def get_coordinator_async():
    """
    Async version of get_coordinator for async contexts.
    """
    return get_coordinator()


def _create_mock_coordinator():
    """
    Create a simple mock coordinator for cases where the full coordinator cannot be initialized.
    """
    class MockJobCoordinator:
        def __init__(self):
            self.active = True
            self.logger = logger
            
        def get_status(self):
            """Get coordinator status"""
            return {
                "active": self.active,
                "queue_size": 0,
                "workers": 0,
                "status": "mock_ready",
                "pending_jobs": 0,
                "results_pending": 0,
                "scheduled_jobs": 0,
                "active_crawlers": 0,
                "satellite_crawlers": {},
                "processing_paused": False,
                "timestamp": datetime.now().isoformat()
            }
            
        def is_healthy(self):
            """Check if coordinator is healthy"""
            return True
            
        async def get_queue_stats(self):
            """Mock queue stats"""
            return self.get_status()
            
        async def pause_job_processing(self):
            """Mock pause"""
            return True
            
        async def resume_job_processing(self):
            """Mock resume"""
            return True

        async def is_processing_paused(self) -> bool:
            """Mock check if processing is paused"""
            return False # Always return False for mock
    
    return MockJobCoordinator()
