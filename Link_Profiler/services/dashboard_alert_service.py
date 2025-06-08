import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import asyncio

from Link_Profiler.config.config_loader import config_loader
from Link_Profiler.database.database import db # Import the singleton instance
import redis.asyncio as redis # Import the module for type hinting
from Link_Profiler.api.schemas import DashboardAlert, AlertSeverity # Assuming this schema is correct
from Link_Profiler.utils.api_quota_manager import APIQuotaManager # Import the concrete APIQuotaManager
from Link_Profiler.monitoring.prometheus_metrics import DASHBOARD_ALERTS_GAUGE, DASHBOARD_ALERTS_TOTAL

logger = logging.getLogger(__name__)

class DashboardAlertService:
    """
    Manages critical alerts specifically for the Mission Control Dashboard.
    These are system-level alerts, distinct from user-defined alert rules.
    """
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(DashboardAlertService, cls).__new__(cls)
        return cls._instance

    def __init__(self, 
                 db: Any, 
                 redis_client: Optional[redis.Redis] = None,
                 api_quota_manager: Optional[APIQuotaManager] = None):
        
        # Ensure _initialized is set to False before calling super().__init__
        # This is crucial for singleton pattern to prevent re-initialization
        if not hasattr(self, '_initialized'):
            self._initialized = False

        if self._initialized:
            return
        self._initialized = True
        
        self.logger = logging.getLogger(__name__ + ".DashboardAlertService")
        self.db = db
        self.redis = redis_client
        self.api_quota_manager = api_quota_manager

        if not self.redis:
            self.logger.warning("No Redis client provided to DashboardAlertService. Creating fallback connection.")
            self.redis = redis.from_url(config_loader.get("redis.url", "redis://localhost:6379/0"))
        
        if not self.redis:
            raise ValueError("DashboardAlertService requires a Redis client.")

        self.satellite_heartbeat_threshold_seconds = config_loader.get("satellite.heartbeat_interval", 5) * 3 # 3 missed heartbeats
        self.queue_overflow_threshold = config_loader.get("queue_system.max_queue_size", 100000) * 0.8 # 80% of max queue size
        self.api_quota_warning_threshold = 75 # % usage
        self.api_quota_critical_threshold = 90 # % usage
        self.api_performance_success_rate_threshold = 0.85 # Below this, trigger warning
        self.api_performance_response_time_threshold_ms = 2000 # Above this, trigger warning

        self._active_alerts: Dict[str, DashboardAlert] = {} # Key: alert_type:id, Value: DashboardAlert

        self.logger.info("DashboardAlertService initialized.")

    async def __aenter__(self):
        """
        Asynchronous context manager entry point.
        No specific async setup needed for this service beyond its dependencies.
        """
        self.logger.info("DashboardAlertService entered context.")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        Asynchronous context manager exit point.
        No specific async teardown needed for this service.
        """
        self.logger.info("DashboardAlertService exited context.")
        pass

    async def check_critical_alerts(self) -> List[DashboardAlert]:
        """
        Checks for various critical system conditions and generates alerts.
        """
        alerts: List[DashboardAlert] = []
        now = datetime.utcnow()

        # Example 1: Redis connection status
        try:
            await self.redis.ping()
        except Exception as e:
            alerts.append(DashboardAlert(
                type="System",
                severity="CRITICAL",
                message=f"Redis connection lost: {e}",
                timestamp=now,
                recommended_action="Check Redis server status and network connectivity."
            ))

        # Example 2: Database connection status
        try:
            self.db.ping()
        except Exception as e:
            alerts.append(DashboardAlert(
                type="System",
                severity="CRITICAL",
                message=f"Database connection lost: {e}",
                timestamp=now,
                recommended_action="Check database server status and credentials."
            ))

        # Example 3: API Quota nearing exhaustion
        if self.api_quota_manager:
            api_statuses = await self.api_quota_manager.get_api_status()
            for api_name, status_data in api_statuses.items():
                if status_data['status'] == "Critical":
                    alerts.append(DashboardAlert(
                        type="API Quota",
                        severity="CRITICAL",
                        message=f"API '{api_name}' quota critically low or exhausted. Used: {status_data['used']}/{status_data['limit']}",
                        timestamp=now,
                        details={"api_name": api_name, "used": status_data['used'], "limit": status_data['limit']},
                        recommended_action="Consider upgrading API plan or reducing usage."
                    ))
                elif status_data['status'] == "Warning":
                    alerts.append(DashboardAlert(
                        type="API Quota",
                        severity="WARNING",
                        message=f"API '{api_name}' quota nearing exhaustion. Used: {status_data['used']}/{status_data['limit']}",
                        timestamp=now,
                        details={"api_name": api_name, "used": status_data['used'], "limit": status_data['limit']},
                        recommended_action="Monitor usage closely or prepare for plan upgrade."
                    ))
                
                # Check for open circuit breakers
                if status_data['performance']['circuit_breaker_state'] == "OPEN":
                    alerts.append(DashboardAlert(
                        type="API Resilience",
                        severity="CRITICAL",
                        message=f"API '{api_name}' circuit breaker is OPEN. Requests are being blocked.",
                        timestamp=now,
                        details={"api_name": api_name, "state": "OPEN"},
                        recommended_action="Investigate external API health or network issues."
                    ))
                elif status_data['performance']['circuit_breaker_state'] == "HALF_OPEN":
                    alerts.append(DashboardAlert(
                        type="API Resilience",
                        severity="WARNING",
                        message=f"API '{api_name}' circuit breaker is HALF_OPEN. Monitoring for recovery.",
                        timestamp=now,
                        details={"api_name": api_name, "state": "HALF_OPEN"},
                        recommended_action="Monitor API health. May indicate intermittent issues."
                    ))

        # Example 4: Unresponsive Satellites (from JobCoordinator's heartbeat data)
        try:
            from Link_Profiler.queue_system.job_coordinator import get_coordinator
            coordinator = await get_coordinator()
            coordinator_stats = await coordinator.get_queue_stats()
            
            heartbeat_key = config_loader.get("queue.heartbeat_queue_sorted_name")
            stale_timeout = config_loader.get("monitoring.crawler_timeout", 30) * 2 # Consider stale after 2 missed heartbeats
            min_timestamp_active = datetime.utcnow().timestamp() - stale_timeout

            all_known_satellites_raw = await self.redis.zrangebyscore(heartbeat_key, '-inf', '+inf', withscores=True)
            
            for satellite_id_bytes, last_heartbeat_ts in all_known_satellites_raw:
                satellite_id = satellite_id_bytes.decode('utf-8')
                if last_heartbeat_ts < min_timestamp_active:
                    alerts.append(DashboardAlert(
                        type="Crawler Fleet",
                        severity="CRITICAL",
                        message=f"Satellite '{satellite_id}' is unresponsive. Last heartbeat: {datetime.fromtimestamp(last_heartbeat_ts).isoformat()}",
                        timestamp=now,
                        details={"satellite_id": satellite_id, "last_heartbeat": datetime.fromtimestamp(last_heartbeat_ts).isoformat()},
                        recommended_action=f"Investigate satellite '{satellite_id}' server or network."
                    ))
        except Exception as e:
            self.logger.error(f"Error checking satellite responsiveness: {e}", exc_info=True)
            alerts.append(DashboardAlert(
                type="System",
                severity="WARNING",
                message=f"Failed to check satellite responsiveness: {e}",
                timestamp=now,
                recommended_action="Check JobCoordinator and Redis heartbeat data."
            ))

        # Example 5: High number of failed jobs in last 24 hours
        twenty_four_hours_ago = now - timedelta(hours=24)
        failed_jobs_24h = self.db.get_crawl_jobs_by_status_and_time(CrawlStatus.FAILED, twenty_four_hours_ago)
        if len(failed_jobs_24h) > config_loader.get("monitoring.failed_jobs_threshold", 10):
            alerts.append(DashboardAlert(
                type="Job Performance",
                severity="CRITICAL",
                message=f"{len(failed_jobs_24h)} jobs failed in the last 24 hours. Exceeds threshold.",
                timestamp=now,
                details={"failed_jobs_count": len(failed_jobs_24h)},
                recommended_action="Review recent failed jobs for common errors."
            ))
        elif len(failed_jobs_24h) > config_loader.get("monitoring.failed_jobs_warning_threshold", 5):
            alerts.append(DashboardAlert(
                type="Job Performance",
                severity="WARNING",
                message=f"{len(failed_jobs_24h)} jobs failed in the last 24 hours. Nearing critical threshold.",
                timestamp=now,
                details={"failed_jobs_count": len(failed_jobs_24h)},
                recommended_action="Monitor job failures closely."
            ))

        self.logger.debug(f"Found {len(alerts)} active dashboard alerts.")
        return alerts

# Singleton instance (will be initialized in main.py)
dashboard_alert_service: Optional['DashboardAlertService'] = None
