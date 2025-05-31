"""
Alert Service - Manages alert rules and triggers notifications based on defined conditions.
File: Link_Profiler/services/alert_service.py
"""

import logging
import asyncio
import re # For regex pattern matching
from datetime import datetime
from typing import List, Dict, Any, Optional, Union
import aiohttp # For sending webhooks (even if just logging for now)

from Link_Profiler.database.database import Database
from Link_Profiler.core.models import AlertRule, CrawlJob, SEOMetrics, AlertSeverity, AlertChannel, serialize_model, CrawlStatus
from Link_Profiler.main import ConnectionManager # New: Import ConnectionManager

logger = logging.getLogger(__name__)

class AlertService:
    """
    Manages alert rules, evaluates conditions, and dispatches notifications.
    """
    def __init__(self, database: Database, connection_manager: Optional[ConnectionManager] = None): # New: Add connection_manager
        self.db = database
        self.active_rules: List[AlertRule] = []
        self._session: Optional[aiohttp.ClientSession] = None # For potential future webhook/HTTP notifications
        self.connection_manager = connection_manager # New: Store ConnectionManager instance
        self.logger = logging.getLogger(__name__)

    async def __aenter__(self):
        """Initialise the service and load active rules."""
        self.logger.info("AlertService starting up. Loading active alert rules.")
        await self.load_active_rules()
        self._session = aiohttp.ClientSession() # Initialize aiohttp session
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Clean up resources."""
        self.logger.info("AlertService shutting down.")
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def load_active_rules(self):
        """Loads all active alert rules from the database."""
        self.active_rules = self.db.get_all_alert_rules(active_only=True)
        self.logger.info(f"Loaded {len(self.active_rules)} active alert rules.")

    async def _send_notification(self, rule: AlertRule, subject: str, message: str, payload: Dict[str, Any]):
        """
        Dispatches a notification based on the rule's configured channels.
        This is a placeholder for actual notification logic (email, Slack, webhook).
        """
        notification_sent = False
        for channel in rule.notification_channels:
            if channel == AlertChannel.DASHBOARD:
                self.logger.info(f"DASHBOARD ALERT [{rule.severity.value.upper()}]: Rule '{rule.name}' triggered. Subject: '{subject}'. Message: '{message}'")
                # New: Send to WebSocket clients
                if self.connection_manager:
                    await self.connection_manager.broadcast({
                        "type": "alert",
                        "rule_id": rule.id,
                        "rule_name": rule.name,
                        "severity": rule.severity.value,
                        "subject": subject,
                        "message": message,
                        "payload": payload,
                        "timestamp": datetime.now().isoformat()
                    })
                notification_sent = True
            elif channel == AlertChannel.WEBHOOK:
                if self._session and rule.notification_recipients:
                    for webhook_url in rule.notification_recipients:
                        try:
                            async with self._session.post(webhook_url, json=payload, timeout=10) as response:
                                response.raise_for_status()
                                self.logger.info(f"WEBHOOK ALERT [{rule.severity.value.upper()}]: Rule '{rule.name}' sent to {webhook_url}. Status: {response.status}")
                                notification_sent = True
                        except aiohttp.ClientError as e:
                            self.logger.error(f"Failed to send webhook for rule '{rule.name}' to {webhook_url}: {e}")
                        except asyncio.TimeoutError:
                            self.logger.warning(f"Webhook to {webhook_url} for rule '{rule.name}' timed out.")
                else:
                    self.logger.warning(f"WEBHOOK ALERT [{rule.severity.value.upper()}]: Rule '{rule.name}' triggered but no webhook URL configured or session not active. Payload: {payload}")
                    notification_sent = True # Logged as "sent" for now
            elif channel == AlertChannel.EMAIL:
                self.logger.info(f"EMAIL ALERT [{rule.severity.value.upper()}]: Rule '{rule.name}' triggered. Subject: '{subject}'. Recipients: {', '.join(rule.notification_recipients)}. Message: '{message}'")
                # Integrate with an email sending library (e.g., aiosmtplib)
                notification_sent = True
            elif channel == AlertChannel.SLACK:
                self.logger.info(f"SLACK ALERT [{rule.severity.value.upper()}]: Rule '{rule.name}' triggered. Subject: '{subject}'. Recipients: {', '.join(rule.notification_recipients)}. Message: '{message}'")
                # Integrate with Slack API
                notification_sent = True
            else:
                self.logger.warning(f"Unknown notification channel '{channel.value}' for rule '{rule.name}'.")
        
        if notification_sent:
            rule.last_triggered_at = datetime.now()
            self.db.save_alert_rule(rule) # Update last_triggered_at in DB

    def _check_condition(self, value: Union[int, float], threshold: Union[int, float], operator: str) -> bool:
        """Evaluates a comparison condition."""
        if operator == ">":
            return value > threshold
        elif operator == "<":
            return value < threshold
        elif operator == ">=":
            return value >= threshold
        elif operator == "<=":
            return value <= threshold
        elif operator == "==":
            return value == threshold
        elif operator == "!=":
            return value != threshold
        else:
            self.logger.warning(f"Unsupported comparison operator: {operator}")
            return False

    async def evaluate_job_update(self, job: CrawlJob):
        """
        Evaluates alert rules based on a crawl job's update.
        Checks for job status changes and detected anomalies.
        """
        for rule in self.active_rules:
            if rule.trigger_type == "job_status_change":
                # Check job type filter
                if rule.job_type_filter and rule.job_type_filter != job.job_type:
                    continue
                # Check target URL pattern
                if rule.target_url_pattern and not re.search(rule.target_url_pattern, job.target_url):
                    continue

                # Check if the job status matches a condition (e.g., FAILED, COMPLETED)
                # For simplicity, assuming rule.metric_name stores the target status string
                if rule.metric_name and job.status.value == rule.metric_name:
                    subject = f"Job {job.id} {job.status.value.upper()}: {job.target_url}"
                    message = f"Crawl job '{job.job_type}' for {job.target_url} has changed status to {job.status.value.upper()}."
                    if job.status == CrawlStatus.FAILED and job.error_log:
                        message += f" Errors: {job.error_log[0].message} (and {job.errors_count - 1} more)."
                    
                    payload = serialize_model(job) # Send full job data in payload
                    await self._send_notification(rule, subject, message, payload)

            elif rule.trigger_type == "anomaly_detected":
                # Check job type filter
                if rule.job_type_filter and rule.job_type_filter != job.job_type:
                    continue
                # Check target URL pattern
                if rule.target_url_pattern and not re.search(rule.target_url_pattern, job.target_url):
                    continue

                # Check if any anomaly in the job matches the rule's filter
                if rule.anomaly_type_filter and job.anomalies_detected:
                    matching_anomalies = [
                        anomaly for anomaly in job.anomalies_detected 
                        if rule.anomaly_type_filter in anomaly
                    ]
                    if matching_anomalies:
                        subject = f"Anomaly Detected in Job {job.id}: {job.target_url}"
                        message = f"Job '{job.job_type}' for {job.target_url} detected anomalies: {', '.join(matching_anomalies)}."
                        
                        payload = serialize_model(job) # Send full job data in payload
                        await self._send_notification(rule, subject, message, payload)

    async def evaluate_seo_metrics_update(self, url: str, metrics: SEOMetrics):
        """
        Evaluates alert rules based on updated SEO metrics for a URL.
        Checks for metric threshold breaches.
        """
        for rule in self.active_rules:
            if rule.trigger_type == "metric_threshold":
                # Check target URL pattern
                if rule.target_url_pattern and not re.search(rule.target_url_pattern, url):
                    continue
                
                # Check if the metric name exists in the SEOMetrics and evaluate condition
                if rule.metric_name and hasattr(metrics, rule.metric_name) and \
                   rule.threshold_value is not None and rule.comparison_operator:
                    
                    metric_value = getattr(metrics, rule.metric_name)
                    if metric_value is None: # Cannot compare if metric value is None
                        continue

                    if self._check_condition(metric_value, rule.threshold_value, rule.comparison_operator):
                        subject = f"Metric Alert: {rule.metric_name} for {url}"
                        message = (f"Alert rule '{rule.name}' triggered: {rule.metric_name} ({metric_value}) "
                                   f"{rule.comparison_operator} {rule.threshold_value} for URL {url}.")
                        
                        payload = serialize_model(metrics) # Send full metrics data in payload
                        payload['url'] = url # Ensure URL is in payload
                        await self._send_notification(rule, subject, message, payload)

    async def evaluate_custom_anomaly(self, anomaly_type: str, target_identifier: str, details: Dict[str, Any]):
        """
        Evaluates alert rules for custom anomalies detected outside of a job context.
        """
        for rule in self.active_rules:
            if rule.trigger_type == "anomaly_detected":
                # Check anomaly type filter
                if rule.anomaly_type_filter and rule.anomaly_type_filter != anomaly_type:
                    continue
                # Check target identifier pattern (assuming it's a URL or domain)
                if rule.target_url_pattern and not re.search(rule.target_url_pattern, target_identifier):
                    continue
                
                subject = f"Custom Anomaly Detected: {anomaly_type} for {target_identifier}"
                message = f"Anomaly '{anomaly_type}' detected for '{target_identifier}'. Details: {details}"
                
                payload = {
                    "anomaly_type": anomaly_type,
                    "target_identifier": target_identifier,
                    "details": details,
                    "timestamp": datetime.now().isoformat()
                }
                await self._send_notification(rule, subject, message, payload)

    async def refresh_rules(self):
        """Periodically refresh active rules in case they are updated in DB."""
        while True:
            await asyncio.sleep(300) # Refresh every 5 minutes
            self.logger.debug("Refreshing alert rules.")
            await self.load_active_rules()
