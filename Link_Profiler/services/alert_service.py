"""
Alert Service - Manages alert rules, evaluates conditions, and dispatches notifications.
File: Link_Profiler/services/alert_service.py
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional, Union
from datetime import datetime, timedelta
import re # For regex pattern matching

from Link_Profiler.database.database import Database
from Link_Profiler.core.models import AlertRule, CrawlJob, CrawlStatus, SEOMetrics, AlertSeverity, AlertChannel # Import AlertChannel and SEOMetrics
from Link_Profiler.config.config_loader import config_loader
from Link_Profiler.utils.connection_manager import ConnectionManager # For WebSocket notifications
from Link_Profiler.monitoring.health_monitor import Alert, AlertLevel # Import Alert and AlertLevel
from Link_Profiler.monitoring.alert_manager import AlertManager # New: Import AlertManager

logger = logging.getLogger(__name__)

class AlertService:
    """
    Manages alert rules, evaluates conditions, and dispatches notifications.
    """
    def __init__(self, db: Database, connection_manager: ConnectionManager, alert_manager: Optional[AlertManager] = None): # New: Accept AlertManager
        self.db = db
        self.connection_manager = connection_manager
        self.alert_manager = alert_manager # Use the injected alert manager
        if self.alert_manager is None:
            # Fallback to a local alert manager if none is provided (e.g., for testing)
            from Link_Profiler.monitoring.alert_manager import AlertManager as LocalAlertManager # Avoid name collision
            self.alert_manager = LocalAlertManager()
            logger.warning("No AlertManager provided to AlertService. Falling back to local AlertManager.")

        self.active_rules: List[AlertRule] = []
        self.last_evaluation_times: Dict[str, datetime] = {} # Track last time a rule was evaluated
        self.cooldown_period_seconds = config_loader.get("monitoring.alert_cooldown", 300) # Default 5 minutes

    async def __aenter__(self):
        """Initializes the AlertService and loads active rules."""
        self.logger.info("AlertService starting up. Loading active alert rules.")
        await self.alert_manager.__aenter__() # Enter AlertManager context
        await self.load_active_rules()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Cleans up AlertService resources."""
        self.logger.info("AlertService shutting down.")
        await self.alert_manager.__aexit__(exc_type, exc_val, exc_tb) # Exit AlertManager context

    async def load_active_rules(self):
        """Loads all active alert rules from the database."""
        try:
            self.active_rules = self.db.get_all_alert_rules(active_only=True)
            self.logger.info(f"Loaded {len(self.active_rules)} active alert rules.")
        except Exception as e:
            self.logger.error(f"Failed to load active alert rules: {e}", exc_info=True)

    async def refresh_rules(self, interval_seconds: int = 300):
        """Periodically refreshes the active alert rules."""
        while True:
            self.logger.debug("Refreshing alert rules.")
            await self.load_active_rules()
            await asyncio.sleep(interval_seconds)

    async def evaluate_job_update(self, job: CrawlJob):
        """
        Evaluates alert rules based on a job update.
        """
        for rule in self.active_rules:
            # Apply rule filters
            if rule.job_type_filter and rule.job_type_filter != job.job_type:
                continue
            if rule.target_url_pattern and not re.search(rule.target_url_pattern, job.target_url):
                continue
            
            # Check cooldown
            if rule.id in self.last_evaluation_times and \
               (datetime.now() - self.last_evaluation_times[rule.id]).total_seconds() < self.cooldown_period_seconds:
                self.logger.debug(f"Rule {rule.name} (ID: {rule.id}) is on cooldown. Skipping evaluation.")
                continue

            alert_triggered = False
            alert_message = ""
            metric_value = None # Initialize metric_value

            if rule.trigger_type == "job_status_change":
                if job.status.value == rule.metric_name: # metric_name is used to store target status
                    alert_triggered = True
                    alert_message = f"Job {job.id} for {job.target_url} changed status to {job.status.value}."
            
            elif rule.trigger_type == "metric_threshold":
                # For job-related metrics, these would typically be in job.results or derived from job properties
                if rule.metric_name == "crawl_errors_rate":
                    total_crawled = job.urls_crawled if job.urls_crawled > 0 else 1
                    metric_value = job.errors_count / total_crawled
                elif rule.metric_name == "progress_percentage":
                    metric_value = job.progress_percentage
                # Add more job-related metrics as needed
                
                if metric_value is not None:
                    if self._check_threshold_condition(metric_value, rule.threshold_value, rule.comparison_operator):
                        alert_triggered = True
                        alert_message = f"Job {job.id} for {job.target_url}: Metric '{rule.metric_name}' ({metric_value:.2f}) crossed threshold {rule.comparison_operator} {rule.threshold_value}."
            
            elif rule.trigger_type == "anomaly_detected":
                if rule.anomaly_type_filter:
                    if rule.anomaly_type_filter in job.anomalies_detected:
                        alert_triggered = True
                        alert_message = f"Job {job.id} for {job.target_url}: Anomaly '{rule.anomaly_type_filter}' detected."
                elif job.anomalies_detected: # Any anomaly detected
                    alert_triggered = True
                    alert_message = f"Job {job.id} for {job.target_url}: Anomalies detected: {', '.join(job.anomalies_detected)}."

            if alert_triggered:
                self.logger.info(f"Alert triggered for rule {rule.name} (ID: {rule.id}): {alert_message}")
                alert = Alert(
                    level=AlertLevel[rule.severity.value.upper()],
                    message=alert_message,
                    metric=rule.metric_name or rule.trigger_type,
                    value=metric_value if metric_value is not None else (job.status.value if rule.trigger_type == "job_status_change" else "N/A"),
                    timestamp=datetime.now().timestamp(),
                    domain=job.target_url # Use target_url as domain for job-related alerts
                )
                await self._send_notification(rule, alert)
                rule.last_triggered_at = datetime.now() # Update last triggered time
                self.last_evaluation_times[rule.id] = datetime.now() # Update last evaluation time for cooldown
                self.db.update_alert_rule(rule) # Persist last triggered time

    async def evaluate_seo_metrics_update(self, url: str, metrics: SEOMetrics):
        """
        Evaluates alert rules based on updated SEO metrics for a URL.
        Checks for metric threshold breaches.
        """
        for rule in self.active_rules:
            # Apply rule filters
            if rule.job_type_filter and rule.job_type_filter != "seo_metrics": # Assuming a job_type_filter for SEO metrics
                continue
            if rule.target_url_pattern and not re.search(rule.target_url_pattern, url):
                continue
            
            # Check cooldown
            if rule.id in self.last_evaluation_times and \
               (datetime.now() - self.last_evaluation_times[rule.id]).total_seconds() < self.cooldown_period_seconds:
                self.logger.debug(f"Rule {rule.name} (ID: {rule.id}) is on cooldown. Skipping evaluation.")
                continue

            alert_triggered = False
            alert_message = ""
            metric_value = None

            if rule.trigger_type == "metric_threshold":
                metric_value = self._get_nested_metric(metrics.to_dict(), rule.metric_name) # Convert SEOMetrics to dict
                
                if metric_value is not None:
                    if self._check_threshold_condition(metric_value, rule.threshold_value, rule.comparison_operator):
                        alert_triggered = True
                        alert_message = f"URL {url}: Metric '{rule.metric_name}' ({metric_value:.2f}) crossed threshold {rule.comparison_operator} {rule.threshold_value}."
            
            if alert_triggered:
                self.logger.info(f"Alert triggered for rule {rule.name} (ID: {rule.id}): {alert_message}")
                alert = Alert(
                    level=AlertLevel[rule.severity.value.upper()],
                    message=alert_message,
                    metric=rule.metric_name,
                    value=metric_value,
                    timestamp=datetime.now().timestamp(),
                    domain=urlparse(url).netloc # Use domain from URL
                )
                await self._send_notification(rule, alert)
                rule.last_triggered_at = datetime.now() # Update last triggered time
                self.last_evaluation_times[rule.id] = datetime.now() # Update last evaluation time for cooldown
                self.db.update_alert_rule(rule) # Persist last triggered time

    async def evaluate_custom_anomaly(self, anomaly_type: str, target_identifier: str, details: Dict[str, Any]):
        """
        Evaluates alert rules for custom anomalies detected outside of a job context.
        """
        for rule in self.active_rules:
            # Apply rule filters
            if rule.job_type_filter and rule.job_type_filter != "custom_anomaly": # Assuming a job_type_filter for custom anomalies
                continue
            if rule.target_url_pattern and not re.search(rule.target_url_pattern, target_identifier):
                continue
            
            # Check cooldown
            if rule.id in self.last_evaluation_times and \
               (datetime.now() - self.last_evaluation_times[rule.id]).total_seconds() < self.cooldown_period_seconds:
                self.logger.debug(f"Rule {rule.name} (ID: {rule.id}) is on cooldown. Skipping evaluation.")
                continue

            alert_triggered = False
            alert_message = ""

            if rule.trigger_type == "anomaly_detected":
                if rule.anomaly_type_filter and rule.anomaly_type_filter == anomaly_type:
                    alert_triggered = True
                    alert_message = f"Custom Anomaly '{anomaly_type}' detected for {target_identifier}. Details: {details}."
                elif not rule.anomaly_type_filter: # Trigger on any custom anomaly if no specific filter
                    alert_triggered = True
                    alert_message = f"Custom Anomaly '{anomaly_type}' detected for {target_identifier}. Details: {details}."
            
            if alert_triggered:
                self.logger.info(f"Alert triggered for rule {rule.name} (ID: {rule.id}): {alert_message}")
                alert = Alert(
                    level=AlertLevel[rule.severity.value.upper()],
                    message=alert_message,
                    metric=anomaly_type,
                    value="N/A", # Value might not be a single number for custom anomalies
                    timestamp=datetime.now().timestamp(),
                    domain=urlparse(target_identifier).netloc if target_identifier.startswith("http") else target_identifier
                )
                await self._send_notification(rule, alert)
                rule.last_triggered_at = datetime.now() # Update last triggered time
                self.last_evaluation_times[rule.id] = datetime.now() # Update last evaluation time for cooldown
                self.db.update_alert_rule(rule) # Persist last triggered time

    async def _send_notification(self, rule: AlertRule, alert: Alert):
        """
        Sends the alert notification through the configured channels using AlertManager.
        """
        await self.alert_manager.dispatch_alert(alert)
