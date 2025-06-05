"""
Real-time Health Monitoring and Alerting System
Monitors crawler health and sends alerts when issues detected
"""

import asyncio
import time
from typing import Dict, List, Any, Callable, Optional
from dataclasses import dataclass
from enum import Enum
import logging
import aiohttp # For webhook_alert_handler

logger = logging.getLogger(__name__)

class AlertLevel(Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"

@dataclass
class Alert:
    level: AlertLevel
    message: str
    metric: str
    value: Any
    timestamp: float
    domain: Optional[str] = None

class HealthMonitor:
    """Real-time health monitoring with alerting"""
    
    def __init__(self, metrics_collector: Any, alert_handlers: List[Callable] = None):
        self.metrics = metrics_collector
        self.alert_handlers = alert_handlers or []
        self.monitoring_active = False
        self.alert_history: List[Alert] = []
        self.alert_cooldowns: Dict[str, float] = {}  # Prevent alert spam
        self.monitor_task: Optional[asyncio.Task] = None
        
        # Health thresholds
        self.thresholds = {
            'success_rate_warning': 0.8,
            'success_rate_critical': 0.5,
            'response_time_warning': 5.0,
            'response_time_critical': 15.0,
            'efficiency_warning': 50.0,
            'efficiency_critical': 20.0,
            'queue_size_warning': 10000,
            'queue_size_critical': 50000
        }
    
    async def start_monitoring(self, interval: float = 30.0):
        """Start continuous health monitoring"""
        if self.monitor_task and not self.monitor_task.done():
            logger.info("Health monitoring already running.")
            return
        self.monitoring_active = True
        self.monitor_task = asyncio.create_task(self._monitor_loop(interval))
        logger.info("Health monitoring started")
    
    async def _monitor_loop(self, interval: float):
        while self.monitoring_active:
            try:
                await self._check_health()
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                logger.info("Health monitoring loop cancelled.")
                break
            except Exception as e:
                logger.error(f"Error in health monitoring loop: {e}")
                await asyncio.sleep(interval) # Still sleep to prevent tight loop on error
    
    def stop_monitoring(self):
        """Stop health monitoring"""
        self.monitoring_active = False
        if self.monitor_task:
            self.monitor_task.cancel()
            self.monitor_task = None
        logger.info("Health monitoring stopped")
    
    async def _check_health(self):
        """Perform health checks and generate alerts"""
        health_report = self.metrics.generate_health_report()
        
        # Update queue metrics (if a queue is available)
        # This assumes the queue object can provide stats to the metrics collector
        # If the queue is managed externally, this might need to be called from there.
        # For now, we'll assume the metrics collector can get this info or it's pushed.
        # await self.metrics.track_queue_metrics(self.metrics.queue_size.get_queue_stats()) # Example if queue stats are directly in metrics

        # Check overall success rate
        success_rate = health_report['overall_health']['success_rate']
        await self._check_threshold('success_rate', success_rate, lower_is_worse=True)
        
        # Check response times
        avg_response_time = health_report['performance']['avg_response_time']
        await self._check_threshold('response_time', avg_response_time, lower_is_worse=False)
        
        # Check efficiency
        efficiency = health_report['overall_health']['efficiency_score']
        await self._check_threshold('efficiency', efficiency, lower_is_worse=True)
        
        # Check queue size
        queue_size = health_report['overall_health']['queue_size']
        await self._check_threshold('queue_size', queue_size, lower_is_worse=False)
        
        # Check per-domain health
        for domain, domain_health in health_report['domain_health'].items():
            await self._check_domain_health(domain, domain_health)
        
        # Update resource metrics
        await self.metrics.track_resource_usage()
    
    async def _check_threshold(self, metric: str, value: float, lower_is_worse: bool = True):
        """Check if metric exceeds thresholds"""
        warning_key = f"{metric}_warning"
        critical_key = f"{metric}_critical"
        
        if warning_key not in self.thresholds:
            return
        
        warning_threshold = self.thresholds[warning_key]
        critical_threshold = self.thresholds.get(critical_key)
        
        alert_level = None
        
        if lower_is_worse:
            # Lower values are worse (success rate, efficiency)
            if critical_threshold is not None and value < critical_threshold:
                alert_level = AlertLevel.CRITICAL
            elif value < warning_threshold:
                alert_level = AlertLevel.WARNING
        else:
            # Higher values are worse (response time, queue size)
            if critical_threshold is not None and value > critical_threshold:
                alert_level = AlertLevel.CRITICAL
            elif value > warning_threshold:
                alert_level = AlertLevel.WARNING
        
        if alert_level:
            await self._send_alert(Alert(
                level=alert_level,
                message=f"{metric.replace('_', ' ').title()}: {value:.2f}",
                metric=metric,
                value=value,
                timestamp=time.time()
            ))
    
    async def _check_domain_health(self, domain: str, domain_health: Dict[str, Any]):
        """Check health metrics for specific domain"""
        success_rate = domain_health['success_rate']
        
        if success_rate < 0.5:
            await self._send_alert(Alert(
                level=AlertLevel.CRITICAL,
                message=f"Domain {domain} critical failure rate: {1-success_rate:.1%}",
                metric="domain_success_rate",
                value=success_rate,
                timestamp=time.time(),
                domain=domain
            ))
        elif success_rate < 0.8:
            await self._send_alert(Alert(
                level=AlertLevel.WARNING,
                message=f"Domain {domain} high failure rate: {1-success_rate:.1%}",
                metric="domain_success_rate",
                value=success_rate,
                timestamp=time.time(),
                domain=domain
            ))
    
    async def _send_alert(self, alert: Alert):
        """Send alert through configured handlers"""
        # Check cooldown to prevent spam
        cooldown_key = f"{alert.metric}_{alert.domain or 'global'}_{alert.level.value}"
        now = time.time()
        
        # Cooldown period (e.g., 5 minutes = 300 seconds)
        cooldown_period = 300 
        if cooldown_key in self.alert_cooldowns:
            if now - self.alert_cooldowns[cooldown_key] < cooldown_period:
                return
        
        self.alert_cooldowns[cooldown_key] = now
        self.alert_history.append(alert)
        
        # Keep only recent alerts
        if len(self.alert_history) > 1000:
            self.alert_history = self.alert_history[-1000:]
        
        logger.warning(f"ALERT [{alert.level.value.upper()}]: {alert.message} (Domain: {alert.domain or 'N/A'})")
        
        # Send through alert handlers
        for handler in self.alert_handlers:
            try:
                await handler(alert)
            except Exception as e:
                logger.error(f"Alert handler failed: {e}")
    
    def get_recent_alerts(self, hours: int = 24) -> List[Alert]:
        """Get alerts from recent time period"""
        cutoff_time = time.time() - (hours * 3600)
        return [alert for alert in self.alert_history if alert.timestamp > cutoff_time]
    
    def add_alert_handler(self, handler: Callable):
        """Add custom alert handler"""
        self.alert_handlers.append(handler)

# Example alert handlers
async def log_alert_handler(alert: Alert):
    """Simple log-based alert handler"""
    logger.warning(f"HEALTH ALERT: {alert.message} (Level: {alert.level.value.upper()})")

async def webhook_alert_handler(alert: Alert, webhook_url: str):
    """Send alerts to webhook endpoint"""
    
    payload = {
        'level': alert.level.value,
        'message': alert.message,
        'metric': alert.metric,
        'value': alert.value,
        'timestamp': alert.timestamp,
        'domain': alert.domain
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(webhook_url, json=payload, timeout=10) as response:
                if response.status != 200:
                    logger.error(f"Webhook alert failed: {response.status} - {await response.text()}")
    except Exception as e:
        logger.error(f"Webhook alert error: {e}")
