# Link_Profiler/services/api_communication_service.py
"""
Advanced API Customer Communication Service
Exceeds industry standards for Ahrefs, SEMrush, Moz, etc.
"""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from enum import Enum
from dataclasses import dataclass

from Link_Profiler.database.database import Database
from Link_Profiler.utils.connection_manager import ConnectionManager
from Link_Profiler.core.models import User
from Link_Profiler.config.config_loader import config_loader

logger = logging.getLogger(__name__)

class CommunicationType(str, Enum):
    EMAIL = "email"
    IN_APP = "in_app"
    WEBHOOK = "webhook"
    SLACK = "slack"
    PUSH = "push"

class NotificationPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class APIEventType(str, Enum):
    QUOTA_WARNING = "quota_warning"
    QUOTA_EXHAUSTED = "quota_exhausted"
    USAGE_SPIKE = "usage_spike"
    API_DEPRECATION = "api_deprecation"
    NEW_FEATURE = "new_feature"
    MAINTENANCE = "maintenance"
    PERFORMANCE_ISSUE = "performance_issue"
    RATE_LIMIT_HIT = "rate_limit_hit"
    UPGRADE_RECOMMENDATION = "upgrade_recommendation"
    COST_OPTIMIZATION = "cost_optimization"

@dataclass
class NotificationTemplate:
    event_type: APIEventType
    priority: NotificationPriority
    channels: List[CommunicationType]
    subject_template: str
    email_template: str
    in_app_template: str
    webhook_payload_template: Dict[str, Any]
    personalization_fields: List[str]

class APICommunicationService:
    """
    Advanced customer communication service that exceeds industry standards.
    Proactive, personalized, and contextual API communications.
    """
    
    def __init__(self, db: Database, connection_manager: ConnectionManager, redis_client=None):
        self.db = db
        self.connection_manager = connection_manager
        self.redis_client = redis_client
        self.logger = logging.getLogger(__name__)
        
        # Load communication preferences from config
        self.email_enabled = config_loader.get("api_communication.email.enabled", True)
        self.webhook_enabled = config_loader.get("api_communication.webhook.enabled", True)
        self.in_app_enabled = config_loader.get("api_communication.in_app.enabled", True)
        
        # Initialize notification templates
        self.templates = self._load_notification_templates()
    
    def _load_notification_templates(self) -> Dict[APIEventType, NotificationTemplate]:
        """Load all notification templates with industry-leading messaging."""
        return {
            APIEventType.QUOTA_WARNING: NotificationTemplate(
                event_type=APIEventType.QUOTA_WARNING,
                priority=NotificationPriority.MEDIUM,
                channels=[CommunicationType.EMAIL, CommunicationType.IN_APP],
                subject_template="⚠️ API Quota Warning: {percentage_used}% used for {api_name}",
                email_template="""
                <h2>API Usage Alert</h2>
                <p>Hi {customer_name},</p>
                <p>You've used <strong>{percentage_used}%</strong> of your {api_name} quota this month.</p>
                
                <div style="background: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0;">
                    <h3>Current Usage:</h3>
                    <ul>
                        <li><strong>Used:</strong> {used_calls:,} calls</li>
                        <li><strong>Remaining:</strong> {remaining_calls:,} calls</li>
                        <li><strong>Resets:</strong> {reset_date}</li>
                    </ul>
                </div>
                
                <h3>💡 Recommendations:</h3>
                <ul>
                    <li>Use <code>?source=cache</code> for faster responses (doesn't count toward quota)</li>
                    <li>Consider upgrading to {next_tier} for {next_tier_quota:,} calls/month</li>
                    <li>Implement request batching for efficiency</li>
                </ul>
                
                <a href="{upgrade_url}" style="background: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Upgrade Plan</a>
                """,
                in_app_template="⚠️ {api_name} quota {percentage_used}% used. {remaining_calls:,} calls remaining.",
                webhook_payload_template={
                    "event": "quota_warning",
                    "api_name": "{api_name}",
                    "used": "{used_calls}",
                    "remaining": "{remaining_calls}",
                    "percentage_used": "{percentage_used}",
                    "reset_date": "{reset_date}"
                },
                personalization_fields=["customer_name", "api_name", "used_calls", "remaining_calls", "percentage_used", "reset_date", "next_tier", "next_tier_quota", "upgrade_url"]
            ),
            
            APIEventType.UPGRADE_RECOMMENDATION: NotificationTemplate(
                event_type=APIEventType.UPGRADE_RECOMMENDATION,
                priority=NotificationPriority.MEDIUM,
                channels=[CommunicationType.EMAIL, CommunicationType.IN_APP],
                subject_template="🚀 Unlock Better Performance: Upgrade Recommendation for {customer_name}",
                email_template="""
                <h2>Performance Optimization Opportunity</h2>
                <p>Hi {customer_name},</p>
                <p>Based on your API usage patterns, we've identified opportunities to improve your performance and reduce costs.</p>
                
                <div style="background: #e7f3ff; padding: 15px; border-radius: 5px; margin: 20px 0;">
                    <h3>Your Usage Analysis (Last 30 Days):</h3>
                    <ul>
                        <li><strong>Live API Calls:</strong> {live_calls:,} ({live_percentage}% of total)</li>
                        <li><strong>Cache Hits:</strong> {cache_calls:,} ({cache_percentage}% of total)</li>
                        <li><strong>Average Response Time:</strong> {avg_response_time}ms</li>
                        <li><strong>Peak Usage Days:</strong> {peak_days}</li>
                    </ul>
                </div>
                
                <h3>💰 Cost Optimization:</h3>
                <p>You could save <strong>${monthly_savings}/month</strong> by:</p>
                <ul>
                    <li>Using cached endpoints for {cache_optimization_percentage}% of your requests</li>
                    <li>Upgrading to {recommended_tier} for better value at your usage level</li>
                    <li>Implementing smart caching in your application</li>
                </ul>
                
                <h3>🚀 Performance Gains:</h3>
                <ul>
                    <li><strong>Response Time:</strong> Up to {performance_improvement}% faster with cache-first approach</li>
                    <li><strong>Reliability:</strong> 99.9%+ uptime for cached responses</li>
                    <li><strong>Rate Limits:</strong> Higher limits with {recommended_tier}</li>
                </ul>
                
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{upgrade_url}" style="background: #28a745; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; font-size: 16px;">Upgrade to {recommended_tier}</a>
                </div>
                
                <p>Questions? Reply to this email or <a href="{support_url}">contact our API specialists</a>.</p>
                """,
                in_app_template="🚀 Save ${monthly_savings}/month with {recommended_tier}. {performance_improvement}% faster responses.",
                webhook_payload_template={
                    "event": "upgrade_recommendation",
                    "recommended_tier": "{recommended_tier}",
                    "monthly_savings": "{monthly_savings}",
                    "performance_improvement": "{performance_improvement}",
                    "usage_analysis": {
                        "live_calls": "{live_calls}",
                        "cache_calls": "{cache_calls}",
                        "avg_response_time": "{avg_response_time}"
                    }
                },
                personalization_fields=["customer_name", "live_calls", "cache_calls", "live_percentage", "cache_percentage", "avg_response_time", "peak_days", "monthly_savings", "cache_optimization_percentage", "recommended_tier", "performance_improvement", "upgrade_url", "support_url"]
            ),
            
            APIEventType.NEW_FEATURE: NotificationTemplate(
                event_type=APIEventType.NEW_FEATURE,
                priority=NotificationPriority.LOW,
                channels=[CommunicationType.EMAIL, CommunicationType.IN_APP],
                subject_template="🎉 New Feature: {feature_name} - Perfect for {use_case}",
                email_template="""
                <h2>New Feature Alert: {feature_name}</h2>
                <p>Hi {customer_name},</p>
                <p>We've just launched <strong>{feature_name}</strong> - a new feature that's perfect for your {use_case} use case!</p>
                
                <div style="background: #f0f8ff; padding: 15px; border-radius: 5px; margin: 20px 0;">
                    <h3>What's New:</h3>
                    <ul>
                        <li><strong>Endpoint:</strong> <code>{new_endpoint}</code></li>
                        <li><strong>Capability:</strong> {feature_description}</li>
                        <li><strong>Performance:</strong> {performance_benefit}</li>
                        <li><strong>Pricing:</strong> {pricing_info}</li>
                    </ul>
                </div>
                
                <h3>🔗 Integration Example:</h3>
                <pre style="background: #f8f9fa; padding: 15px; border-radius: 5px; overflow-x: auto;">
{code_example}
                </pre>
                
                <h3>📚 Resources:</h3>
                <ul>
                    <li><a href="{docs_url}">API Documentation</a></li>
                    <li><a href="{examples_url}">Code Examples</a></li>
                    <li><a href="{video_url}">Video Tutorial</a></li>
                </ul>
                
                <p><strong>Available Now:</strong> This feature is immediately available on your {current_tier} plan.</p>
                """,
                in_app_template="🎉 New: {feature_name} is now available! Perfect for {use_case}.",
                webhook_payload_template={
                    "event": "new_feature",
                    "feature_name": "{feature_name}",
                    "endpoint": "{new_endpoint}",
                    "description": "{feature_description}",
                    "available_on_plan": "{current_tier}"
                },
                personalization_fields=["customer_name", "feature_name", "use_case", "new_endpoint", "feature_description", "performance_benefit", "pricing_info", "code_example", "docs_url", "examples_url", "video_url", "current_tier"]
            ),
            
            APIEventType.PERFORMANCE_ISSUE: NotificationTemplate(
                event_type=APIEventType.PERFORMANCE_ISSUE,
                priority=NotificationPriority.HIGH,
                channels=[CommunicationType.EMAIL, CommunicationType.IN_APP, CommunicationType.WEBHOOK],
                subject_template="🔧 API Performance Issue Detected & Resolved",
                email_template="""
                <h2>Performance Issue Resolution</h2>
                <p>Hi {customer_name},</p>
                <p>We detected and resolved a performance issue affecting the <strong>{affected_endpoint}</strong> endpoint.</p>
                
                <div style="background: #fff3cd; padding: 15px; border-radius: 5px; margin: 20px 0;">
                    <h3>Issue Summary:</h3>
                    <ul>
                        <li><strong>Affected Endpoint:</strong> {affected_endpoint}</li>
                        <li><strong>Issue Period:</strong> {start_time} - {end_time}</li>
                        <li><strong>Impact:</strong> {impact_description}</li>
                        <li><strong>Affected Requests:</strong> {affected_requests} calls</li>
                    </ul>
                </div>
                
                <div style="background: #d4edda; padding: 15px; border-radius: 5px; margin: 20px 0;">
                    <h3>✅ Resolution:</h3>
                    <p>{resolution_description}</p>
                    <p><strong>Current Status:</strong> All systems operating normally</p>
                </div>
                
                <h3>💰 Service Credit:</h3>
                <p>We've automatically applied a <strong>${service_credit}</strong> credit to your account for the inconvenience.</p>
                
                <h3>🛡️ Prevention Measures:</h3>
                <ul>
                    <li>{prevention_measure_1}</li>
                    <li>{prevention_measure_2}</li>
                    <li>{prevention_measure_3}</li>
                </ul>
                
                <p>Thank you for your patience. Questions? Contact our support team anytime.</p>
                """,
                in_app_template="✅ Performance issue resolved for {affected_endpoint}. ${service_credit} credit applied.",
                webhook_payload_template={
                    "event": "performance_issue_resolved",
                    "endpoint": "{affected_endpoint}",
                    "duration_minutes": "{duration_minutes}",
                    "affected_requests": "{affected_requests}",
                    "service_credit": "{service_credit}",
                    "status": "resolved"
                },
                personalization_fields=["customer_name", "affected_endpoint", "start_time", "end_time", "impact_description", "affected_requests", "resolution_description", "service_credit", "prevention_measure_1", "prevention_measure_2", "prevention_measure_3", "duration_minutes"]
            )
        }
    
    async def send_notification(self, user: User, event_type: APIEventType, context: Dict[str, Any]) -> bool:
        """Send a personalized notification to a user based on event type."""
        template = self.templates.get(event_type)
        if not template:
            self.logger.error(f"No template found for event type: {event_type}")
            return False
        
        # Get user communication preferences
        user_preferences = await self._get_user_preferences(user.id)
        
        # Personalize the message
        personalized_context = await self._personalize_context(user, context)
        
        success = True
        
        # Send via enabled channels based on user preferences
        for channel in template.channels:
            if channel in user_preferences.get('enabled_channels', template.channels):
                try:
                    if channel == CommunicationType.EMAIL:
                        await self._send_email(user, template, personalized_context)
                    elif channel == CommunicationType.IN_APP:
                        await self._send_in_app(user, template, personalized_context)
                    elif channel == CommunicationType.WEBHOOK:
                        await self._send_webhook(user, template, personalized_context)
                    elif channel == CommunicationType.SLACK:
                        await self._send_slack(user, template, personalized_context)
                except Exception as e:
                    self.logger.error(f"Failed to send {channel} notification to user {user.id}: {e}")
                    success = False
        
        # Log the notification
        await self._log_notification(user.id, event_type, template.priority, success)
        
        return success
    
    async def analyze_usage_and_recommend(self, user: User) -> Optional[Dict[str, Any]]:
        """Analyze user's API usage and generate intelligent recommendations."""
        # Get 30-day usage data
        usage_data = await self._get_usage_analytics(user.id, days=30)
        
        if not usage_data:
            return None
        
        recommendations = {
            "cost_optimization": [],
            "performance_optimization": [],
            "feature_recommendations": []
        }
        
        # Analyze cache vs live usage
        live_percentage = usage_data.get('live_calls', 0) / max(usage_data.get('total_calls', 1), 1) * 100
        if live_percentage > 70:
            potential_savings = self._calculate_cache_savings(usage_data)
            recommendations["cost_optimization"].append({
                "type": "cache_optimization",
                "description": f"Use cached endpoints for {100-live_percentage:.0f}% cost reduction",
                "potential_savings": potential_savings,
                "implementation": "Add ?source=cache to your requests for non-critical data"
            })
        
        # Analyze usage tier efficiency
        current_tier = self._get_user_tier(user)
        optimal_tier = self._calculate_optimal_tier(usage_data)
        if optimal_tier != current_tier:
            recommendations["cost_optimization"].append({
                "type": "tier_optimization",
                "description": f"Switch to {optimal_tier} for better value",
                "current_tier": current_tier,
                "recommended_tier": optimal_tier,
                "monthly_savings": self._calculate_tier_savings(usage_data, current_tier, optimal_tier)
            })
        
        # Feature recommendations based on usage patterns
        if usage_data.get('domain_analysis_calls', 0) > 100:
            recommendations["feature_recommendations"].append({
                "feature": "bulk_domain_analysis",
                "description": "Process multiple domains in single request",
                "benefit": "Up to 60% faster processing for bulk operations"
            })
        
        return recommendations if any(recommendations.values()) else None
    
    async def monitor_quota_usage(self):
        """Background task to monitor all users' quota usage and send proactive alerts."""
        users = self.db.get_all_users()
        
        for user in users:
            try:
                quota_status = await self._get_quota_status(user.id)
                
                # Check for quota warnings
                for api_name, status in quota_status.items():
                    percentage_used = status['percentage_used']
                    
                    # Send warnings at 75%, 90%, and 95%
                    if percentage_used >= 75 and not status.get('warned_75'):
                        await self.send_notification(user, APIEventType.QUOTA_WARNING, {
                            'api_name': api_name,
                            'percentage_used': percentage_used,
                            'used_calls': status['used'],
                            'remaining_calls': status['remaining'],
                            'reset_date': status['reset_date']
                        })
                        await self._mark_quota_warning_sent(user.id, api_name, 75)
                    
                    # Check for upgrade recommendations
                    if percentage_used >= 80:
                        recommendations = await self.analyze_usage_and_recommend(user)
                        if recommendations:
                            await self.send_notification(user, APIEventType.UPGRADE_RECOMMENDATION, recommendations)
                
            except Exception as e:
                self.logger.error(f"Error monitoring quota for user {user.id}: {e}")
    
    async def _send_email(self, user: User, template: NotificationTemplate, context: Dict[str, Any]):
        """Send email notification using connection manager."""
        subject = template.subject_template.format(**context)
        body = template.email_template.format(**context)
        
        await self.connection_manager.send_email(
            to_email=user.email,
            subject=subject,
            html_body=body,
            priority=template.priority.value
        )
    
    async def _send_in_app(self, user: User, template: NotificationTemplate, context: Dict[str, Any]):
        """Send in-app notification via WebSocket or Redis pub/sub."""
        message = template.in_app_template.format(**context)
        
        notification = {
            "id": f"notif_{datetime.utcnow().timestamp()}",
            "user_id": user.id,
            "type": template.event_type.value,
            "priority": template.priority.value,
            "message": message,
            "timestamp": datetime.utcnow().isoformat(),
            "read": False
        }
        
        # Store in Redis for persistence
        if self.redis_client:
            await self.redis_client.lpush(f"notifications:{user.id}", str(notification))
            await self.redis_client.publish(f"user_notifications:{user.id}", str(notification))
    
    async def _send_webhook(self, user: User, template: NotificationTemplate, context: Dict[str, Any]):
        """Send webhook notification to user's configured endpoint."""
        webhook_url = await self._get_user_webhook_url(user.id)
        if not webhook_url:
            return
        
        payload = {}
        for key, value_template in template.webhook_payload_template.items():
            payload[key] = value_template.format(**context)
        
        await self.connection_manager.send_webhook(webhook_url, payload)
    
    async def _get_user_preferences(self, user_id: str) -> Dict[str, Any]:
        """Get user's communication preferences."""
        # This would typically come from the database
        # For now, return default preferences
        return {
            "enabled_channels": [CommunicationType.EMAIL, CommunicationType.IN_APP],
            "email_frequency": "immediate",
            "quiet_hours": {"start": "22:00", "end": "08:00"},
            "timezone": "UTC"
        }
    
    async def _personalize_context(self, user: User, context: Dict[str, Any]) -> Dict[str, Any]:
        """Add personalization data to the context."""
        personalized = context.copy()
        personalized.update({
            "customer_name": user.username,
            "current_tier": self._get_user_tier(user),
            "support_url": "https://support.linkprofiler.com",
            "upgrade_url": f"https://billing.linkprofiler.com/upgrade?user={user.id}",
            "docs_url": "https://docs.linkprofiler.com"
        })
        return personalized
    
    def _get_user_tier(self, user: User) -> str:
        """Get user's subscription tier."""
        # This would integrate with your billing system
        return getattr(user, 'tier', 'basic')
    
    async def _get_usage_analytics(self, user_id: str, days: int = 30) -> Dict[str, Any]:
        """Get comprehensive usage analytics for a user."""
        # This would query your analytics system
        return {
            "total_calls": 5000,
            "live_calls": 3500,
            "cache_calls": 1500,
            "avg_response_time": 450,
            "peak_days": ["Monday", "Wednesday"],
            "domain_analysis_calls": 150,
            "backlink_calls": 2000,
            "keyword_calls": 1000
        }
    
    async def _log_notification(self, user_id: str, event_type: APIEventType, priority: NotificationPriority, success: bool):
        """Log notification for analytics and debugging."""
        log_entry = {
            "user_id": user_id,
            "event_type": event_type.value,
            "priority": priority.value,
            "success": success,
            "timestamp": datetime.utcnow().isoformat()
        }
        self.logger.info(f"Notification logged: {log_entry}")

# Global singleton instance
api_communication_service = None

async def get_api_communication_service(db: Database, connection_manager: ConnectionManager, redis_client=None) -> APICommunicationService:
    """Get or create the global API communication service instance."""
    global api_communication_service
    if api_communication_service is None:
        api_communication_service = APICommunicationService(db, connection_manager, redis_client)
    return api_communication_service