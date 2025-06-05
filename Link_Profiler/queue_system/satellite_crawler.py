import asyncio
import logging
import os
import sys
import uuid
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

import redis.asyncio as redis
import aiohttp # For potential future API calls from satellite
import psutil # For CPU/Memory usage in heartbeat

# --- Robust Project Root Discovery ---
# Assuming this file is at Link_Profiler/queue_system/satellite_crawler.py
# The project root (containing setup.py) is two levels up from this file.
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if project_root and project_root not in sys.path:
    sys.path.insert(0, project_root)
    print(f"PROJECT_ROOT (discovered and added to sys.path): {project_root}")
else:
    print(f"PROJECT_ROOT (discovery failed or already in sys.path): {project_root}")

# Import necessary components from the Link_Profiler package
from Link_Profiler.config.config_loader import ConfigLoader
from Link_Profiler.utils.logging_config import setup_logging, get_default_logging_config
from Link_Profiler.crawlers.web_crawler import EnhancedWebCrawler # Changed to EnhancedWebCrawler
from Link_Profiler.core.models import CrawlConfig, CrawlJob, CrawlStatus, serialize_model, CrawlError, SEOMetrics
from Link_Profiler.services.ai_service import AIService # Import AIService for WebCrawler
from Link_Profiler.queue_system.smart_crawler_queue import SmartCrawlQueue # Import SmartCrawlQueue for internal use by WebCrawler
from Link_Profiler.utils.distributed_circuit_breaker import DistributedResilienceManager # New: Import DistributedResilienceManager

# --- Configuration and Logging Setup ---
config_loader = ConfigLoader()
# Load config from the Link_Profiler/config directory
config_loader.load_config(config_dir=os.path.join(project_root, "Link_Profiler", "config"), env_var_prefix="LP_")

# Setup logging for the satellite
satellite_log_level = config_loader.get("satellite.logging.level", "INFO")
satellite_logging_config = config_loader.get("satellite.logging.config", get_default_logging_config(satellite_log_level))
setup_logging(satellite_logging_config)
logger = logging.getLogger(__name__)

class SatelliteCrawler:
    def __init__(self):
        self.crawler_id = config_loader.get("satellite.id", str(uuid.uuid4()))
        self.redis_url = config_loader.get("redis.url")
        self.heartbeat_interval = config_loader.get("satellite.heartbeat_interval", 5)
        self.job_queue_name = config_loader.get("queue.job_queue_name", "crawl_jobs")
        self.result_queue_name = config_loader.get("queue.result_queue_name", "crawl_results")
        self.dead_letter_queue_name = config_loader.get("queue.dead_letter_queue_name", "dead_letter_queue")
        self.control_channel_prefix = "crawler_control" # For specific commands
        self.global_control_channel = "crawler_control:all" # For global commands
        self.current_code_version = config_loader.get("system.current_code_version", "unknown")
        self.processing_paused = False # Local flag for pausing job processing
        self.cancel_current_job: bool = False  # Flag set when a CANCEL_JOB command is received

        self.redis_client: Optional[redis.Redis] = None
        self.web_crawler: Optional[EnhancedWebCrawler] = None # Changed to EnhancedWebCrawler
        self.ai_service: Optional[AIService] = None # AI service for content analysis
        self.smart_crawl_queue: Optional[SmartCrawlQueue] = None # Smart crawl queue for internal use by WebCrawler
        self.resilience_manager: Optional[DistributedResilienceManager] = None # New: DistributedResilienceManager

        self.jobs_processed = 0
        self.current_job_id: Optional[str] = None
        self.running = True
        self._start_time = datetime.now() # For uptime calculation

        logger.info(f"Satellite Crawler '{self.crawler_id}' initialized.")
        logger.info(f"Redis URL: {self.redis_url}")
        logger.info(f"Current Code Version: {self.current_code_version}")

    async def __aenter__(self):
        self.redis_client = redis.Redis(connection_pool=redis.ConnectionPool.from_url(self.redis_url))
        try:
            await self.redis_client.ping()
            logger.info("Connected to Redis successfully.")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise

        # Initialize AI Service
        self.ai_service = AIService()
        await self.ai_service.__aenter__() # Enter AI service context

        # Initialize SmartCrawlQueue for internal use by WebCrawler
        # Note: This SmartCrawlQueue is for the WebCrawler's internal link discovery,
        # not the main job queue managed by the coordinator.
        self.smart_crawl_queue = SmartCrawlQueue(redis_client=self.redis_client)
        await self.smart_crawl_queue.__aenter__()

        # New: Initialize DistributedResilienceManager
        self.resilience_manager = DistributedResilienceManager(redis_client=self.redis_client)
        await self.resilience_manager.__aenter__()

        # Initialize WebCrawler with loaded config and AI service
        crawler_config_data = config_loader.get("crawler", {})
        # Ensure ml_rate_optimization is set based on rate_limiting config
        crawler_config_data['ml_rate_optimization'] = config_loader.get("rate_limiting.ml_enhanced", False)
        # Pass relevant anti_detection settings to CrawlConfig
        crawler_config_data['user_agent_rotation'] = config_loader.get("anti_detection.user_agent_rotation", False)
        crawler_config_data['request_header_randomization'] = config_loader.get("anti_detection.request_header_randomization", False)
        crawler_config_data['human_like_delays'] = config_loader.get("anti_detection.human_like_delays", False)
        crawler_config_data['stealth_mode'] = config_loader.get("anti_detection.stealth_mode", False)
        crawler_config_data['browser_fingerprint_randomization'] = config_loader.get("anti_detection.browser_fingerprint_randomization", False)
        crawler_config_data['captcha_solving_enabled'] = config_loader.get("anti_detection.captcha_solving_enabled", False)
        crawler_config_data['anomaly_detection_enabled'] = config_loader.get("anti_detection.anomaly_detection_enabled", False)
        crawler_config_data['use_proxies'] = config_loader.get("proxy.use_proxies", False)
        crawler_config_data['proxy_list'] = config_loader.get("proxy.proxy_list", [])
        crawler_config_data['render_javascript'] = config_loader.get("browser_crawler.enabled", False)
        crawler_config_data['browser_type'] = config_loader.get("browser_crawler.browser_type", "chromium")
        crawler_config_data['headless_browser'] = config_loader.get("browser_crawler.headless", True)

        main_crawl_config = CrawlConfig(**crawler_config_data)
        self.web_crawler = EnhancedWebCrawler(
            config=main_crawl_config, 
            crawl_queue=self.smart_crawl_queue, 
            ai_service=self.ai_service,
            resilience_manager=self.resilience_manager # New: Pass the distributed resilience manager
        )
        await self.web_crawler.__aenter__() # Enter WebCrawler context

        # Start background tasks
        asyncio.create_task(self._heartbeat_loop())
        asyncio.create_task(self._control_command_listener())
        asyncio.create_task(self._global_control_command_listener())

        logger.info(f"Satellite Crawler '{self.crawler_id}' started successfully.")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.running = False
        logger.info(f"Satellite Crawler '{self.crawler_id}' shutting down...")
        if self.web_crawler:
            await self.web_crawler.__aexit__(exc_type, exc_val, exc_tb)
        if self.resilience_manager: # New: Exit DistributedResilienceManager context
            await self.resilience_manager.__aexit__(exc_type, exc_val, exc_tb)
        if self.ai_service:
            await self.ai_service.__aexit__(exc_type, exc_val, exc_tb)
        if self.smart_crawl_queue:
            await self.smart_crawl_queue.__aexit__(exc_type, exc_val, exc_tb)
        if self.redis_client:
            await self.redis_client.close()
        logger.info(f"Satellite Crawler '{self.crawler_id}' shutdown complete.")

    async def _heartbeat_loop(self):
        """Sends periodic heartbeats to the coordinator."""
        heartbeat_key_sorted = config_loader.get("queue.heartbeat_queue_sorted_name", "crawler_heartbeats_sorted")
        heartbeat_details_key = f"crawler_details:{self.crawler_id}"
        
        while self.running:
            try:
                timestamp = datetime.now().timestamp()
                
                # Store detailed heartbeat data in a separate key
                heartbeat_data = {
                    "id": self.crawler_id,
                    "last_seen": datetime.now().isoformat(),
                    "status": "running" if not self.processing_paused else "paused",
                    "jobs_processed": self.jobs_processed,
                    "current_job_id": self.current_job_id,
                    "cpu_usage": psutil.cpu_percent(interval=None),
                    "memory_usage": psutil.virtual_memory().percent,
                    "code_version": self.current_code_version,
                    "uptime_seconds": (datetime.now() - self._start_time).total_seconds()
                }
                await self.redis_client.set(heartbeat_details_key, json.dumps(heartbeat_data), ex=self.heartbeat_interval * 3) # Expire after 3 intervals
                
                # Update sorted set with timestamp for quick active crawler lookup
                await self.redis_client.zadd(heartbeat_key_sorted, {self.crawler_id: timestamp})
                
                logger.debug(f"Heartbeat sent for '{self.crawler_id}'.")
            except Exception as e:
                logger.error(f"Error sending heartbeat for '{self.crawler_id}': {e}")
            finally:
                await asyncio.sleep(self.heartbeat_interval)

    async def _control_command_listener(self):
        """Listens for specific control commands from the coordinator via Pub/Sub."""
        channel = f"{self.control_channel_prefix}:{self.crawler_id}"
        logger.info(f"Subscribing to control channel: {channel}")
        pubsub = self.redis_client.pubsub()
        await pubsub.subscribe(channel)
        try:
            while self.running:
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message and message.get("type") == "message":
                    try:
                        data = json.loads(message["data"].decode("utf-8"))
                    except Exception:
                        logger.warning(f"Malformed control message: {message}")
                        continue
                    command = data.get("command")
                    payload = data.get("payload")
                    logger.info(
                        f"Received command '{command}' for crawler {self.crawler_id}")
                    await self._execute_command(command, payload)
                await asyncio.sleep(0.1)
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.close()

    async def _global_control_command_listener(self):
        """Listens for global control commands from the coordinator via Pub/Sub."""
        channel = self.global_control_channel
        logger.info(f"Subscribing to global control channel: {channel}")
        pubsub = self.redis_client.pubsub()
        await pubsub.subscribe(channel)
        try:
            while self.running:
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message and message.get("type") == "message":
                    try:
                        data = json.loads(message["data"].decode("utf-8"))
                    except Exception:
                        logger.warning(f"Malformed global control message: {message}")
                        continue
                    command = data.get("command")
                    payload = data.get("payload")
                    logger.info(f"Received global command '{command}'")
                    await self._execute_command(command, payload)
                await asyncio.sleep(0.5)
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.close()

    async def _execute_command(self, command: str, payload: Optional[Dict[str, Any]] = None):
        """Executes a received control command."""
        if command == "PAUSE":
            self.processing_paused = True
            logger.info(f"Crawler '{self.crawler_id}' paused job processing.")
        elif command == "RESUME":
            self.processing_paused = False
            logger.info(f"Crawler '{self.crawler_id}' resumed job processing.")
        elif command == "SHUTDOWN":
            logger.info(f"Crawler '{self.crawler_id}' received SHUTDOWN command. Exiting.")
            self.running = False
        elif command == "RESTART":
            logger.info(f"Crawler '{self.crawler_id}' received RESTART command. Initiating restart.")
            # A simple way to restart is to exit and rely on external process manager (e.g., Docker, systemd)
            # to restart the script. For a more graceful in-process restart, you'd need more complex logic.
            self.running = False
            # Optionally, re-execute the current script
            # os.execv(sys.executable, ['python'] + sys.argv)
        elif command == "CANCEL_JOB":
            job_id = payload.get("job_id") if payload else None
            if job_id and job_id == self.current_job_id:
                logger.info(f"Cancellation requested for active job {job_id}.")
                self.cancel_current_job = True
            else:
                logger.info(
                    f"Received CANCEL_JOB for {job_id}, but current job is {self.current_job_id}.")
        else:
            logger.warning(f"Unknown command received: {command}")

    async def run(self):
        """Main loop for the satellite crawler."""
        logger.info(f"Satellite Crawler '{self.crawler_id}' main loop started.")
        
        while self.running:
            if self.processing_paused:
                logger.debug("Processing paused. Waiting...")
                await asyncio.sleep(5)
                continue

            try:
                # Blocking pop from the job queue with a timeout
                # ZPOPMAX pops the highest score (highest priority)
                job_data_list = await self.redis_client.bzpopmax(self.job_queue_name, timeout=1)
                
                if job_data_list:
                    _queue_name, job_json, _score = job_data_list
                    job_dict = json.loads(job_json)
                    job = CrawlJob.from_dict(job_dict)
                    self.current_job_id = job.id
                    logger.info(f"Pulled job {job.id} (type: {job.job_type}) for {job.target_url} from queue.")

                    # Execute the crawl job
                    result_summary = await self._execute_crawl_job(job)

                    # If a cancellation was requested for this job, override status
                    if self.cancel_current_job:
                        result_summary["status"] = CrawlStatus.CANCELLED.value
                        result_summary["error_message"] = "Job cancelled by coordinator"
                        self.cancel_current_job = False

                    # Send result back to coordinator
                    await self._send_result_to_coordinator(job, result_summary)
                    
                    self.jobs_processed += 1
                    self.current_job_id = None
                else:
                    logger.debug("No jobs in queue. Waiting...")
                    await asyncio.sleep(1) # Short sleep if no jobs to avoid busy-waiting

            except Exception as e:
                logger.error(f"Error in main satellite loop for '{self.crawler_id}': {e}", exc_info=True)
                # If an error occurs while processing a job, mark it as failed and send to DLQ
                if self.current_job_id:
                    failed_job = CrawlJob(
                        id=self.current_job_id,
                        target_url=job.target_url if 'job' in locals() else "unknown",
                        job_type=job.job_type if 'job' in locals() else "unknown",
                        status=CrawlStatus.FAILED,
                        created_date=job.created_date if 'job' in locals() else datetime.now(),
                        config=job.config if 'job' in locals() else CrawlConfig(),
                        error_log=[CrawlError(url=job.target_url if 'job' in locals() else "unknown", error_type="SatelliteProcessingError", message=str(e))]
                    )
                    await self._send_result_to_coordinator(failed_job, {"error_message": str(e)})
                    self.current_job_id = None
                await asyncio.sleep(5) # Wait before retrying main loop

    async def _execute_crawl_job(self, job: CrawlJob) -> Dict[str, Any]:
        """Executes the actual crawl using the WebCrawler."""
        logger.info(f"Executing crawl for job {job.id}: {job.target_url}")
        try:
            # The WebCrawler's start_crawl method now handles the internal queueing
            # and crawling logic based on the provided initial_seed_urls and config.
            # It returns a final CrawlResult summary.
            final_crawl_result = await self.web_crawler.start_crawl(
                target_url=job.target_url,
                initial_seed_urls=job.initial_seed_urls,
                job_id=job.id
            )
            
            # Prepare summary for coordinator
            summary = {
                "job_id": job.id,
                "status": CrawlStatus.COMPLETED.value,
                "urls_crawled": final_crawl_result.pages_crawled,
                "links_found": final_crawl_result.total_links_found, # Assuming WebCrawler tracks this
                "progress_percentage": 100.0,
                "results": serialize_model(final_crawl_result), # Send the full result object
                "error_message": None
            }
            logger.info(f"Job {job.id} completed by satellite. Crawled {final_crawl_result.pages_crawled} pages.")
            return summary

        except Exception as e:
            logger.error(f"Crawl job {job.id} failed during execution: {e}", exc_info=True)
            error_summary = {
                "job_id": job.id,
                "status": CrawlStatus.FAILED.value,
                "urls_crawled": 0,
                "links_found": 0,
                "progress_percentage": job.progress_percentage, # Keep last known progress
                "error_message": str(e),
                "failed_url": job.target_url,
                "error_log": [serialize_model(CrawlError(url=job.target_url, error_type="CrawlExecutionError", message=str(e)))]
            }
            return error_summary

    async def _send_result_to_coordinator(self, job: CrawlJob, result_summary: Dict[str, Any]):
        """Sends the job result summary back to the coordinator."""
        try:
            # Add some satellite metadata to the result
            result_summary["satellite_id"] = self.crawler_id
            result_summary["satellite_version"] = self.current_code_version
            
            await self.redis_client.rpush(self.result_queue_name, json.dumps(result_summary))
            logger.info(f"Result for job {job.id} sent to coordinator.")
        except Exception as e:
            logger.error(f"Failed to send result for job {job.id} to coordinator: {e}", exc_info=True)
            # If result cannot be sent, push to dead letter queue
            await self._send_to_dead_letter_queue(job.id, result_summary, f"Failed to send result: {e}")

    async def _send_to_dead_letter_queue(self, job_id: str, original_data: Dict[str, Any], reason: str):
        """Pushes a failed job or result to the dead-letter queue."""
        dlq_message = {
            "job_id": job_id,
            "original_data": original_data,
            "dead_letter_reason": reason,
            "dead_letter_timestamp": datetime.now().isoformat()
        }
        try:
            await self.redis_client.rpush(self.dead_letter_queue_name, json.dumps(dlq_message))
            logger.error(f"Job {job_id} pushed to dead-letter queue. Reason: {reason}")
        except Exception as e:
            logger.critical(f"CRITICAL: Failed to push job {job_id} to dead-letter queue: {e}", exc_info=True)

# --- Main execution block ---
async def main():
    satellite = SatelliteCrawler()
    async with satellite:
        await satellite.run()

if __name__ == "__main__":
    # Ensure the project root is in sys.path for imports to work
    # This is duplicated from the top of the file to ensure it runs even if the script is executed directly
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    # Set up basic logging for the main function before full config is loaded
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Satellite Crawler stopped by user (KeyboardInterrupt).")
    except Exception as e:
        logger.critical(f"Satellite Crawler encountered a critical error: {e}", exc_info=True)
        sys.exit(1)

