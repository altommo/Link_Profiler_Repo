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
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, db: Any, redis_client: redis.Redis, api_quota_manager: APIQuotaManager):
        if self._initialized:
            return
        self._initialized = True
        self.logger = logging.getLogger(__name__ + ".DashboardAlertService")
        self.db = db
        self.redis = redis_client
        self.api_quota_manager = api_quota_manager

        self.satellite_heartbeat_threshold_seconds = config_loader.get("satellite.heartbeat_interval", 5) * 3 # 3 missed heartbeats
        self.queue_overflow_threshold = config_loader.get("queue_system.max_queue_size", 100000) * 0.8 # 80% of max queue size
        self.api_quota_warning_threshold = 75 # % usage
        self.api_quota_critical_threshold = 90 # % usage
        self.api_performance_success_rate_threshold = 0.85 # Below this, trigger warning
        self.api_performance_response_time_threshold_ms = 2000 # Above this, trigger warning

        self._active_alerts: Dict[str, DashboardAlert] = {} # Key: alert_type:id, Value: DashboardAlert

    async def check_critical_alerts(self) -> List[DashboardAlert]:
        """
        Checks for various critical system conditions and generates alerts.
        """
        new_alerts: List[DashboardAlert] = []
        
        # 1. Satellite failure detection
        satellite_alerts = await self._detect_failed_satellites()
        new_alerts.extend(satellite_alerts)

        # 2. Queue overflow detection
        queue_alerts = await self._check_queue_overflow()
        new_alerts.extend(queue_alerts)

        # 3. API quota exhaustion warning
        api_quota_alerts = await self._check_api_quotas()
        new_alerts.extend(api_quota_alerts)

        # 4. API performance degradation
        api_performance_alerts = self._check_api_performance_degradation()
        new_alerts.extend(api_performance_alerts)

        # Update active alerts and Prometheus metrics
        self._update_active_alerts(new_alerts)
        self._update_prometheus_metrics()

        return list(self._active_alerts.values())

    async def _detect_failed_satellites(self) -> List[DashboardAlert]:
        """Detects unresponsive satellite crawlers based on heartbeats."""
        alerts: List[DashboardAlert] = []
        heartbeat_key = config_loader.get("queue.heartbeat_queue_sorted_name")
        
        # Get all active satellites from Redis sorted set
        # Score is timestamp, so get all entries with score > (now - threshold)
        now_timestamp = datetime.utcnow().timestamp()
        min_timestamp = now_timestamp - self.satellite_heartbeat_threshold_seconds
        
        active_satellites_raw = await self.redis.zrangebyscore(heartbeat_key, min_timestamp, now_timestamp, withscores=True)
        
        active_satellite_ids = {s.decode('utf-8') for s, _ in active_satellites_raw}
        
        # Get all known satellites (e.g., from a config or a persistent store if you track them)
        # For now, let's assume we can get a list of all expected satellites from the coordinator
        # or by inspecting past heartbeats. This is a simplification.
        # In a real system, you might have a registry of satellites.
        
        # Let's get all satellites that have sent a heartbeat in the last 24 hours
        all_known_satellites_raw = await self.redis.zrangebyscore(heartbeat_key, now_timestamp - timedelta(hours=24).total_seconds(), now_timestamp, withscores=False)
        all_known_satellite_ids = {s.decode('utf-8') for s in all_known_satellites_raw}

        unresponsive_satellites = all_known_satellite_ids.difference(active_satellite_ids)

        for satellite_id in unresponsive_satellites:
            alert_id = f"satellite_failure:{satellite_id}"
            # Only add if not already active and not already in the list of alerts to be returned
            if alert_id not in self._active_alerts and not any(a.type == "satellite_failure" and a.details.get("satellite_id") == satellite_id for a in alerts): 
                alert = DashboardAlert(
                    type="satellite_failure",
                    severity=AlertSeverity.CRITICAL,
                    message=f"Satellite '{satellite_id}' is unresponsive. Last heartbeat: {datetime.fromtimestamp(await self.redis.zscore(heartbeat_key, satellite_id) or 0).strftime('%Y-%m-%d %H:%M:%S UTC') if await self.redis.exists(heartbeat_key) and await self.redis.zscore(heartbeat_key, satellite_id) else 'N/A'}.",
                    affected_jobs=[], # Placeholder: would need to query jobs assigned to this satellite
                    recommended_action="Investigate satellite host or network connectivity.",
                    details={"satellite_id": satellite_id}
                )
                alerts.append(alert)
                DASHBOARD_ALERTS_TOTAL.labels(alert_type="satellite_failure", severity=AlertSeverity.CRITICAL.value).inc()
                self.logger.warning(f"CRITICAL ALERT: {alert.message}")
        
        # Also clear alerts for satellites that have become responsive
        for alert_id in list(self._active_alerts.keys()):
            if alert_id.startswith("satellite_failure:"):
                satellite_id = alert_id.split(":")[1]
                if satellite_id in active_satellite_ids:
                    self.logger.info(f"Satellite '{satellite_id}' is now responsive. Clearing alert.")
                    self._active_alerts.pop(alert_id)

        return alerts

    async def _check_queue_overflow(self) -> List[DashboardAlert]:
        """Checks if the job queue is overflowing."""
        alerts: List[DashboardAlert] = []
        job_queue_name = config_loader.get("queue.job_queue_name")
        queue_depth = await self.redis.llen(job_queue_name)
        
        if queue_depth >= self.queue_overflow_threshold:
            alert_id = "queue_overflow"
            if alert_id not in self._active_alerts:
                alert = DashboardAlert(
                    type="queue_overflow",
                    severity=AlertSeverity.WARNING,
                    message=f"Job queue depth ({queue_depth}) is approaching overflow threshold ({self.queue_overflow_threshold}).",
                    recommended_action="Scale up satellite fleet or reduce job submission rate.",
                    details={"queue_depth": queue_depth, "threshold": self.queue_overflow_threshold}
                )
                alerts.append(alert)
                DASHBOARD_ALERTS_TOTAL.labels(alert_type="queue_overflow", severity=AlertSeverity.WARNING.value).inc()
                self.logger.warning(f"WARNING ALERT: {alert.message}")
        else:
            # Clear alert if queue is no longer overflowing
            if "queue_overflow" in self._active_alerts:
                self.logger.info("Queue depth is back to normal. Clearing queue overflow alert.")
                self._active_alerts.pop("queue_overflow")

        return alerts

    async def _check_api_quotas(self) -> List[DashboardAlert]:
        """Checks API quotas and generates warnings/critical alerts."""
        alerts: List[DashboardAlert] = []
        api_statuses_dict = await self.api_quota_manager.get_api_status() # Await this call

        for api_name, api_status_data in api_statuses_dict.items():
            percentage_used = api_status_data["percentage_used"]
            
            alert_id_warning = f"api_quota_warning:{api_name}"
            alert_id_critical = f"api_quota_critical:{api_name}"

            if percentage_used >= self.api_quota_critical_threshold:
                if alert_id_critical not in self._active_alerts:
                    alert = DashboardAlert(
                        type="api_quota_exhaustion",
                        severity=AlertSeverity.CRITICAL,
                        message=f"API '{api_name}' quota is CRITICAL ({percentage_used:.2f}% used).",
                        recommended_action="Investigate usage or upgrade plan.",
                        details=api_status_data
                    )
                    alerts.append(alert)
                    DASHBOARD_ALERTS_TOTAL.labels(alert_type="api_quota_exhaustion", severity=AlertSeverity.CRITICAL.value).inc()
                    self.logger.critical(f"CRITICAL ALERT: {alert.message}")
                # If critical, ensure warning is cleared
                if alert_id_warning in self._active_alerts:
                    self._active_alerts.pop(alert_id_warning)
            elif percentage_used >= self.api_quota_warning_threshold:
                # Only add warning if not already active and not already a critical alert
                if alert_id_warning not in self._active_alerts and alert_id_critical not in self._active_alerts:
                    alert = DashboardAlert(
                        type="api_quota_exhaustion",
                        severity=AlertSeverity.WARNING,
                        message=f"API '{api_name}' quota is WARNING ({percentage_used:.2f}% used).",
                        recommended_action="Monitor usage closely.",
                        details=api_status_data
                    )
                    alerts.append(alert)
                    DASHBOARD_ALERTS_TOTAL.labels(alert_type="api_quota_exhaustion", severity=AlertSeverity.WARNING.value).inc()
                    self.logger.warning(f"WARNING ALERT: {alert.message}")
            else:
                # Clear alerts if usage is below thresholds
                if alert_id_warning in self._active_alerts:
                    self.logger.info(f"API '{api_name}' usage is back to normal. Clearing warning alert.")
                    self._active_alerts.pop(alert_id_warning)
                if alert_id_critical in self._active_alerts:
                    self.logger.info(f"API '{api_name}' usage is back to normal. Clearing critical alert.")
                    self._active_alerts.pop(alert_id_critical)
        
        return alerts

    def _check_api_performance_degradation(self) -> List[DashboardAlert]:
        """Checks API performance metrics and generates alerts for degradation."""
        alerts: List[DashboardAlert] = []
        # api_quota_manager.get_api_status() is an async method, but this method is sync.
        # This will need to be refactored if real-time performance checks are critical here.
        # For now, it will use the last known state from api_quota_manager's internal cache.
        api_statuses_dict = self.api_quota_manager.get_api_status_sync() # Assuming a sync method or cached data

        for api_name, api_status_data in api_statuses_dict.items():
            performance = api_status_data.get("performance", {})
            success_rate = performance.get("success_rate", 1.0)
            avg_response_time_ms = performance.get("average_response_time_ms", 0.0)
            total_calls = performance.get("total_calls", 0)

            # Only alert if there's enough data to make a judgment
            if total_calls < 10: # Require at least 10 calls to assess performance
                continue

            alert_id_low_success = f"api_performance_low_success:{api_name}"
            alert_id_high_response_time = f"api_performance_high_response_time:{api_name}"

            # Check for low success rate
            if success_rate < self.api_performance_success_rate_threshold:
                if alert_id_low_success not in self._active_alerts:
                    alert = DashboardAlert(
                        type="api_performance_degradation",
                        severity=AlertSeverity.WARNING,
                        message=f"API '{api_name}' success rate is low ({success_rate:.2f}).",
                        recommended_action="Investigate API stability or switch to alternative.",
                        details=api_status_data
                    )
                    alerts.append(alert)
                    DASHBOARD_ALERTS_TOTAL.labels(alert_type="api_performance_degradation", severity=AlertSeverity.WARNING.value).inc()
                    self.logger.warning(f"WARNING ALERT: {alert.message}")
            else:
                if alert_id_low_success in self._active_alerts:
                    self.logger.info(f"API '{api_name}' success rate recovered. Clearing alert.")
                    self._active_alerts.pop(alert_id_low_success)

            # Check for high response time
            if avg_response_time_ms > self.api_performance_response_time_threshold_ms:
                if alert_id_high_response_time not in self._active_alerts:
                    alert = DashboardAlert(
                        type="api_performance_degradation",
                        severity=AlertSeverity.WARNING,
                        message=f"API '{api_name}' average response time is high ({avg_response_time_ms:.0f}ms).",
                        recommended_action="Investigate API latency or switch to alternative.",
                        details=api_status_data
                    )
                    alerts.append(alert)
                    DASHBOARD_ALERTS_TOTAL.labels(alert_type="api_performance_degradation", severity=AlertSeverity.WARNING.value).inc()
                    self.logger.warning(f"WARNING ALERT: {alert.message}")
            else:
                if alert_id_high_response_time in self._active_alerts:
                    self.logger.info(f"API '{api_name}' response time recovered. Clearing alert.")
                    self._active_alerts.pop(alert_id_high_response_time)
        
        return alerts

    def _update_active_alerts(self, new_alerts: List[DashboardAlert]):
        """Updates the internal dictionary of active alerts."""
        # Add new alerts
        for alert in new_alerts:
            # Create a unique key for the alert based on its type and specific details
            alert_key_parts = [alert.type]
            if alert.type == "satellite_failure" and alert.details and "satellite_id" in alert.details:
                alert_key_parts.append(alert.details["satellite_id"])
            elif alert.type == "api_quota_exhaustion" and alert.details and "api_name" in alert.details:
                alert_key_parts.append(alert.details["api_name"])
            elif alert.type == "api_performance_degradation" and alert.details and "api_name" in alert.details:
                alert_key_parts.append(alert.details["api_name"])
            
            alert_key = ":".join(alert_key_parts)
            self._active_alerts[alert_key] = alert

        # Remove alerts that are no longer active (not in new_alerts)
        current_alert_keys = {":".join([a.type] + ([a.details["satellite_id"]] if a.type == "satellite_failure" and a.details and "satellite_id" in a.details else []) + ([a.details["api_name"]] if a.type == "api_quota_exhaustion" and a.details and "api_name" in a.details else []) + ([a.details["api_name"]] if a.type == "api_performance_degradation" and a.details and "api_name" in a.details else [])) for a in new_alerts}
        keys_to_remove = [key for key in self._active_alerts if key not in current_alert_keys]
        for key in keys_to_remove:
            self.logger.info(f"Clearing alert: {self._active_alerts[key].message}")
            self._active_alerts.pop(key)


    def _update_prometheus_metrics(self):
        """Updates Prometheus gauges for active alerts."""
        # Reset gauges for all known alert types and severities
        # This is a more robust way to ensure gauges reflect current state
        # You might need to iterate over known label combinations or reset all
        # For simplicity, we'll just set the active ones.
        # A full reset would require knowing all possible label combinations.
        
        # Clear all existing gauge values first (if possible, or rely on setting to 0)
        # This is tricky with Prometheus client library if labels are dynamic.
        # For now, we'll just ensure active alerts are set to 1.
        
        # Set current active alerts
        for alert in self._active_alerts.values():
            alert_type = alert.type
            severity = alert.severity.value
            DASHBOARD_ALERTS_GAUGE.labels(alert_type=alert_type, severity=severity).set(1) # Set to 1 if active
        
        # For alerts that are no longer active, ensure their gauge is set to 0
        # This requires tracking previous states or iterating all possible labels.
        # A simpler approach for dynamic labels is to only set active ones,
        # and rely on Prometheus's scrape interval to eventually drop old series
        # if they are no longer reported.
        # For critical alerts, you might want to explicitly set to 0 when resolved.
        # This is a placeholder for more sophisticated Prometheus metric management.

# Singleton instance (will be initialized in main.py)
dashboard_alert_service: Optional['DashboardAlertService'] = None
