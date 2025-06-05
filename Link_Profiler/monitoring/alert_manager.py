"""
Advanced Alerting System - Manages multi-channel notifications for alerts.
Supports various notification channels like Slack, Email, Webhooks.
"""

import logging
import asyncio
from typing import List, Dict, Any, Optional
import aiohttp
import json
from datetime import datetime
from email.message import EmailMessage
import aiosmtplib

from Link_Profiler.config.config_loader import config_loader
from Link_Profiler.monitoring.health_monitor import Alert, AlertLevel # Import Alert and AlertLevel

logger = logging.getLogger(__name__)

class AlertManager:
    """
    Manages the dispatch of alerts to various configured channels.
    """
    def __init__(self):
        self.logger = logging.getLogger(__name__ + ".AlertManager")
        self.webhook_enabled = config_loader.get("notifications.webhooks.enabled", False)
        self.webhook_urls = config_loader.get("notifications.webhooks.urls", [])
        self.email_enabled = config_loader.get("notifications.email.enabled", False)
        self.slack_enabled = config_loader.get("notifications.slack.enabled", False)
        self.slack_webhook_url = config_loader.get("notifications.slack.webhook_url")

        self._session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        """Initializes the aiohttp ClientSession for sending notifications."""
        if self.webhook_enabled or self.slack_enabled:
            if self._session is None or self._session.closed:
                self._session = aiohttp.ClientSession()
                self.logger.info("AlertManager aiohttp client session created.")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Closes the aiohttp ClientSession."""
        if self._session and not self._session.closed:
            self.logger.info("Closing AlertManager aiohttp client session.")
            await self._session.close()
            self._session = None

    async def dispatch_alert(self, alert: Alert):
        """
        Dispatches an alert to all configured and relevant notification channels.
        """
        self.logger.info(f"Dispatching alert: {alert.message} (Level: {alert.level.value})")

        tasks = []
        if self.webhook_enabled:
            for url in self.webhook_urls:
                tasks.append(self._send_webhook_alert(alert, url))
        
        if self.slack_enabled and self.slack_webhook_url:
            tasks.append(self._send_slack_alert(alert, self.slack_webhook_url))
        
        if self.email_enabled:
            # Email sending typically requires an SMTP client setup
            # For now, this is a placeholder.
            self.logger.warning("Email alerting is enabled but not implemented yet.")
            # tasks.append(self._send_email_alert(alert))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        else:
            self.logger.warning(f"No active notification channels configured for alert: {alert.message}")

    async def _send_webhook_alert(self, alert: Alert, webhook_url: str):
        """Sends an alert to a generic webhook endpoint."""
        if not self._session:
            self.logger.error("Webhook session not initialized. Cannot send webhook alert.")
            return

        payload = {
            'level': alert.level.value,
            'message': alert.message,
            'metric': alert.metric,
            'value': alert.value,
            'timestamp': datetime.fromtimestamp(alert.timestamp).isoformat(),
            'domain': alert.domain
        }
        
        try:
            async with self._session.post(webhook_url, json=payload, timeout=10) as response:
                response.raise_for_status()
                self.logger.info(f"Successfully sent webhook alert for '{alert.metric}' to {webhook_url}. Status: {response.status}")
        except aiohttp.ClientError as e:
            self.logger.error(f"Failed to send webhook alert for '{alert.metric}' to {webhook_url}: {e}", exc_info=True)
        except asyncio.TimeoutError:
            self.logger.warning(f"Webhook to {webhook_url} for '{alert.metric}' timed out.")
        except Exception as e:
            self.logger.error(f"Unexpected error sending webhook alert for '{alert.metric}' to {webhook_url}: {e}", exc_info=True)

    async def _send_slack_alert(self, alert: Alert, slack_webhook_url: str):
        """Sends an alert to Slack via a webhook."""
        if not self._session:
            self.logger.error("Slack session not initialized. Cannot send Slack alert.")
            return

        color_map = {
            AlertLevel.INFO: "#439FE0",
            AlertLevel.WARNING: "#FFA500",
            AlertLevel.CRITICAL: "#FF0000"
        }
        
        payload = {
            "attachments": [
                {
                    "fallback": f"[{alert.level.value.upper()}] {alert.message}",
                    "color": color_map.get(alert.level, "#CCCCCC"),
                    "pretext": f"Link Profiler Alert: {alert.level.value.upper()}",
                    "title": alert.message,
                    "fields": [
                        {"title": "Metric", "value": str(alert.value), "short": True},
                        {"title": "Timestamp", "value": datetime.fromtimestamp(alert.timestamp).strftime("%Y-%m-%d %H:%M:%S UTC"), "short": True}
                    ],
                    "footer": "Link Profiler Monitoring",
                    "ts": alert.timestamp
                }
            ]
        }
        if alert.domain:
            payload["attachments"][0]["fields"].append({"title": "Domain", "value": alert.domain, "short": True})

        try:
            async with self._session.post(slack_webhook_url, json=payload, timeout=10) as response:
                response.raise_for_status()
                self.logger.info(f"Successfully sent Slack alert for '{alert.metric}'. Status: {response.status}")
        except aiohttp.ClientError as e:
            self.logger.error(f"Failed to send Slack alert for '{alert.metric}': {e}", exc_info=True)
        except asyncio.TimeoutError:
            self.logger.warning(f"Slack webhook for '{alert.metric}' timed out.")
        except Exception as e:
            self.logger.error(f"Unexpected error sending Slack alert for '{alert.metric}': {e}", exc_info=True)

    async def _send_email_alert(self, alert: Alert):
        """Send an email alert using an SMTP server."""

        smtp_server = config_loader.get("notifications.email.smtp_server")
        smtp_port = config_loader.get("notifications.email.smtp_port", 587)
        smtp_username = config_loader.get("notifications.email.smtp_username")
        smtp_password = config_loader.get("notifications.email.smtp_password")
        sender_email = config_loader.get("notifications.email.sender_email")

        recipients = getattr(alert, "recipients", None)

        if not all([smtp_server, smtp_port, sender_email, recipients]):
            self.logger.error("Email configuration or recipients missing for alert.")
            return

        msg = EmailMessage()
        msg["Subject"] = f"Link Profiler Alert: {alert.level.value.upper()} - {alert.message}"
        msg["From"] = sender_email
        msg["To"] = ", ".join(recipients)
        msg.set_content(
            f"Metric: {alert.metric}\n"
            f"Value: {alert.value}\n"
            f"Timestamp: {datetime.fromtimestamp(alert.timestamp).isoformat()}\n"
            f"Domain: {alert.domain or 'N/A'}"
        )

        try:
            await aiosmtplib.send(
                msg,
                hostname=smtp_server,
                port=int(smtp_port),
                username=smtp_username,
                password=smtp_password,
                start_tls=True,
            )
            self.logger.info(f"Email alert sent for {alert.metric}.")
        except aiosmtplib.SMTPException as e:
            self.logger.error(
                f"Failed to send email alert for {alert.metric}: {e}",
                exc_info=True,
            )
        except Exception as e:
            self.logger.error(
                f"Unexpected error sending email alert for {alert.metric}: {e}",
                exc_info=True,
            )

# Create a singleton instance
alert_manager = AlertManager()
