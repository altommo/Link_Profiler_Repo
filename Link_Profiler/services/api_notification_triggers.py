# Link_Profiler/services/api_notification_triggers.py
"""
API Notification Trigger System
Handles automated detection and manual triggers for API change communications
"""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from enum import Enum
from dataclasses import dataclass
import json

from Link_Profiler.database.database import Database
from Link_Profiler.services.api_communication_service import APICommunicationService, APIEventType
from Link_Profiler.core.models import User
from Link_Profiler.config.config_loader import config_loader

logger = logging.getLogger(__name__)

@dataclass
class APIChangeNotification:
    """Represents a scheduled API change notification"""
    id: str
    event_type: APIEventType
    title: str
    description: str
    affected_endpoints: List[str]
    severity: str  # "low", "medium", "high", "critical"
    scheduled_date: datetime
    notification_date: datetime
    target_users: str  # "all", "basic+", "pro+", "enterprise"
    status: str  # "draft", "scheduled", "sent", "cancelled"
    created_by: str
    created_at: datetime
    metadata: Dict[str, Any]

class APINotificationTriggers:
    """
    Manages both automated detection and manual triggers for API communications
    """
    
    def __init__(self, db: Database, communication_service: APICommunicationService, redis_client=None):
        self.db = db
        self.communication_service = communication_service
        self.redis_client = redis_client
        self.logger = logging.getLogger(__name__)
        
        # Load configuration
        self.auto_detection_enabled = config_loader.get("api_notifications.auto_detection.enabled", True)
        self.performance_threshold = config_loader.get("api_notifications.performance_threshold_ms", 5000)
        self.error_rate_threshold = config_loader.get("api_notifications.error_rate_threshold", 0.05)
    
    # =============================================================================
    # MANUAL ADMIN TRIGGERS
    # =============================================================================
    
    async def schedule_api_deprecation_notice(
        self,
        admin_user: User,
        deprecated_endpoints: List[str],
        deprecation_date: datetime,
        replacement_info: Dict[str, str],
        advance_notice_days: int = 30
    ) -> str:
        """
        Manually schedule an API deprecation notice
        
        Args:
            admin_user: Admin user scheduling the notice
            deprecated_endpoints: List of endpoints being deprecated
            deprecation_date: When the endpoints will be deprecated
            replacement_info: Mapping of old endpoint -> new endpoint
            advance_notice_days: How many days in advance to notify
        
        Returns:
            notification_id: ID of the scheduled notification
        """
        notification_id = f"api_deprecation_{datetime.utcnow().timestamp()}"
        notification_date = deprecation_date - timedelta(days=advance_notice_days)
        
        # Create notification record
        notification = APIChangeNotification(
            id=notification_id,
            event_type=APIEventType.API_DEPRECATION,
            title=f"API Deprecation Notice: {len(deprecated_endpoints)} endpoints",
            description=f"The following endpoints will be deprecated on {deprecation_date.strftime('%B %d, %Y')}",
            affected_endpoints=deprecated_endpoints,
            severity="high",
            scheduled_date=deprecation_date,
            notification_date=notification_date,
            target_users="all",
            status="scheduled",
            created_by=admin_user.id,
            created_at=datetime.utcnow(),
            metadata={
                "replacement_info": replacement_info,
                "advance_notice_days": advance_notice_days,
                "migration_guide_url": f"https://docs.linkprofiler.com/migration/{notification_id}"
            }
        )
        
        # Store in database
        await self._store_notification(notification)
        
        # Schedule the notification
        await self._schedule_notification_job(notification)
        
        self.logger.info(f"API deprecation notice scheduled by {admin_user.username} for {len(deprecated_endpoints)} endpoints")
        
        return notification_id
    
    async def schedule_maintenance_notice(
        self,
        admin_user: User,
        maintenance_start: datetime,
        maintenance_end: datetime,
        affected_services: List[str],
        impact_description: str,
        advance_notice_hours: int = 24
    ) -> str:
        """
        Schedule a maintenance window notification
        """
        notification_id = f"maintenance_{datetime.utcnow().timestamp()}"
        notification_date = maintenance_start - timedelta(hours=advance_notice_hours)
        
        duration_hours = (maintenance_end - maintenance_start).total_seconds() / 3600
        
        notification = APIChangeNotification(
            id=notification_id,
            event_type=APIEventType.MAINTENANCE,
            title=f"Scheduled Maintenance: {duration_hours:.1f} hour window",
            description=impact_description,
            affected_endpoints=affected_services,
            severity="medium",
            scheduled_date=maintenance_start,
            notification_date=notification_date,
            target_users="all",
            status="scheduled",
            created_by=admin_user.id,
            created_at=datetime.utcnow(),
            metadata={
                "maintenance_end": maintenance_end.isoformat(),
                "estimated_duration_hours": duration_hours,
                "impact_level": "partial" if len(affected_services) < 5 else "full",
                "status_page_url": "https://status.linkprofiler.com"
            }
        )
        
        await self._store_notification(notification)
        await self._schedule_notification_job(notification)
        
        self.logger.info(f"Maintenance notice scheduled by {admin_user.username} for {maintenance_start}")
        
        return notification_id
    
    async def send_immediate_performance_alert(
        self,
        admin_user: User,
        affected_endpoints: List[str],
        issue_description: str,
        resolution_eta: Optional[datetime] = None,
        service_credit: Optional[float] = None
    ) -> str:
        """
        Send immediate performance issue notification
        """
        notification_id = f"performance_alert_{datetime.utcnow().timestamp()}"
        
        # Get all affected users
        affected_users = await self._get_users_using_endpoints(affected_endpoints)
        
        # Send notifications immediately
        for user in affected_users:
            context = {
                "affected_endpoint": ", ".join(affected_endpoints),
                "start_time": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
                "impact_description": issue_description,
                "resolution_description": f"ETA: {resolution_eta.strftime('%H:%M UTC') if resolution_eta else 'Investigating'}",
                "service_credit": service_credit or 0,
                "affected_requests": await self._count_user_requests_to_endpoints(user.id, affected_endpoints),
                "prevention_measure_1": "Enhanced monitoring deployed",
                "prevention_measure_2": "Auto-scaling improvements implemented", 
                "prevention_measure_3": "Circuit breaker patterns enhanced"
            }
            
            await self.communication_service.send_notification(
                user, 
                APIEventType.PERFORMANCE_ISSUE, 
                context
            )
        
        self.logger.info(f"Immediate performance alert sent by {admin_user.username} to {len(affected_users)} users")
        
        return notification_id
    
    async def announce_new_feature(
        self,
        admin_user: User,
        feature_name: str,
        new_endpoints: List[str],
        feature_description: str,
        target_user_tier: str = "all",
        code_examples: Dict[str, str] = None
    ) -> str:
        """
        Announce a new API feature to users
        """
        notification_id = f"new_feature_{datetime.utcnow().timestamp()}"
        
        # Get targeted users based on tier
        target_users = await self._get_users_by_tier(target_user_tier)
        
        for user in target_users:
            # Personalize based on user's usage patterns
            use_case = await self._determine_user_use_case(user.id)
            
            context = {
                "feature_name": feature_name,
                "use_case": use_case,
                "new_endpoint": new_endpoints[0] if new_endpoints else "Multiple endpoints",
                "feature_description": feature_description,
                "performance_benefit": "Up to 40% faster processing",
                "pricing_info": "Included in your current plan",
                "code_example": self._generate_code_example(new_endpoints[0], user) if new_endpoints else "",
                "docs_url": f"https://docs.linkprofiler.com/features/{feature_name.lower().replace(' ', '-')}",
                "examples_url": f"https://docs.linkprofiler.com/examples/{feature_name.lower().replace(' ', '-')}",
                "video_url": f"https://tutorials.linkprofiler.com/{feature_name.lower().replace(' ', '-')}"
            }
            
            await self.communication_service.send_notification(
                user,
                APIEventType.NEW_FEATURE,
                context
            )
        
        self.logger.info(f"New feature announcement sent by {admin_user.username} to {len(target_users)} users")
        
        return notification_id
    
    # =============================================================================
    # AUTOMATED DETECTION SYSTEMS
    # =============================================================================
    
    async def start_automated_monitoring(self):
        """Start background tasks for automated API monitoring"""
        if not self.auto_detection_enabled:
            self.logger.info("Automated API monitoring disabled by configuration")
            return
        
        # Start monitoring tasks
        asyncio.create_task(self._monitor_api_performance())
        asyncio.create_task(self._monitor_quota_usage())
        asyncio.create_task(self._monitor_usage_patterns())
        asyncio.create_task(self._process_scheduled_notifications())
        
        self.logger.info("Automated API monitoring tasks started")
    
    async def _monitor_api_performance(self):
        """Monitor API performance and trigger alerts for issues"""
        while True:
            try:
                # Check performance metrics from Redis or monitoring system
                performance_data = await self._get_performance_metrics()
                
                for endpoint, metrics in performance_data.items():
                    avg_response_time = metrics.get('avg_response_time_ms', 0)
                    error_rate = metrics.get('error_rate', 0)
                    
                    # Check for performance degradation
                    if avg_response_time > self.performance_threshold:
                        await self._trigger_performance_alert(
                            endpoint,
                            f"Average response time: {avg_response_time}ms (threshold: {self.performance_threshold}ms)",
                            metrics
                        )
                    
                    # Check for high error rates
                    if error_rate > self.error_rate_threshold:
                        await self._trigger_error_rate_alert(
                            endpoint,
                            f"Error rate: {error_rate:.2%} (threshold: {self.error_rate_threshold:.2%})",
                            metrics
                        )
                
                # Sleep for 5 minutes before next check
                await asyncio.sleep(300)
                
            except Exception as e:
                self.logger.error(f"Error in performance monitoring: {e}")
                await asyncio.sleep(60)  # Shorter sleep on error
    
    async def _monitor_quota_usage(self):
        """Monitor user quota usage and send proactive notifications"""
        while True:
            try:
                users = self.db.get_all_users()
                
                for user in users:
                    # This integrates with your existing quota monitoring
                    quota_status = await self._get_user_quota_status(user.id)
                    
                    for api_name, status in quota_status.items():
                        percentage_used = status.get('percentage_used', 0)
                        
                        # Send upgrade recommendations for heavy users
                        if percentage_used >= 80:
                            recommendations = await self.communication_service.analyze_usage_and_recommend(user)
                            if recommendations:
                                await self.communication_service.send_notification(
                                    user,
                                    APIEventType.UPGRADE_RECOMMENDATION,
                                    recommendations
                                )
                
                # Check every hour
                await asyncio.sleep(3600)
                
            except Exception as e:
                self.logger.error(f"Error in quota monitoring: {e}")
                await asyncio.sleep(300)
    
    async def _monitor_usage_patterns(self):
        """Monitor usage patterns to identify optimization opportunities"""
        while True:
            try:
                # Analyze daily usage patterns
                usage_analysis = await self._analyze_daily_usage_patterns()
                
                for user_id, analysis in usage_analysis.items():
                    if analysis.get('optimization_opportunity_score', 0) > 0.7:
                        user = self.db.get_user_by_id(user_id)
                        if user:
                            context = {
                                "monthly_savings": analysis.get('potential_monthly_savings', 0),
                                "cache_optimization_percentage": analysis.get('cache_opportunity_percentage', 0),
                                "recommended_tier": analysis.get('optimal_tier', 'pro'),
                                "performance_improvement": analysis.get('performance_gain_percentage', 0)
                            }
                            
                            await self.communication_service.send_notification(
                                user,
                                APIEventType.COST_OPTIMIZATION,
                                context
                            )
                
                # Run daily at 9 AM UTC
                await asyncio.sleep(86400)
                
            except Exception as e:
                self.logger.error(f"Error in usage pattern monitoring: {e}")
                await asyncio.sleep(3600)
    
    async def _process_scheduled_notifications(self):
        """Process and send scheduled notifications"""
        while True:
            try:
                # Get notifications scheduled for now
                due_notifications = await self._get_due_notifications()
                
                for notification in due_notifications:
                    await self._send_scheduled_notification(notification)
                
                # Check every 5 minutes
                await asyncio.sleep(300)
                
            except Exception as e:
                self.logger.error(f"Error processing scheduled notifications: {e}")
                await asyncio.sleep(60)
    
    # =============================================================================
    # HELPER METHODS
    # =============================================================================
    
    async def _store_notification(self, notification: APIChangeNotification):
        """Store notification in database"""
        # This would store in your database
        if self.redis_client:
            await self.redis_client.hset(
                f"api_notifications:{notification.id}",
                mapping={
                    "data": json.dumps(notification.__dict__, default=str)
                }
            )
    
    async def _schedule_notification_job(self, notification: APIChangeNotification):
        """Schedule notification for future sending"""
        if self.redis_client:
            # Add to scheduled notifications sorted set
            await self.redis_client.zadd(
                "scheduled_notifications",
                {notification.id: notification.notification_date.timestamp()}
            )
    
    async def _get_users_using_endpoints(self, endpoints: List[str]) -> List[User]:
        """Get users who have recently used the specified endpoints"""
        # This would query your usage analytics
        return self.db.get_all_users()  # Simplified for now
    
    async def _count_user_requests_to_endpoints(self, user_id: str, endpoints: List[str]) -> int:
        """Count recent requests from user to specific endpoints"""
        # This would query your analytics system
        return 42  # Placeholder
    
    async def _get_users_by_tier(self, tier: str) -> List[User]:
        """Get users by subscription tier"""
        all_users = self.db.get_all_users()
        if tier == "all":
            return all_users
        # Filter by tier - this would integrate with your billing system
        return [user for user in all_users if getattr(user, 'tier', 'basic') == tier]
    
    async def _determine_user_use_case(self, user_id: str) -> str:
        """Determine user's primary use case based on API usage"""
        # Analyze usage patterns to determine use case
        usage_patterns = await self._get_user_usage_patterns(user_id)
        
        if usage_patterns.get('backlink_calls', 0) > usage_patterns.get('keyword_calls', 0):
            return "link building and SEO analysis"
        elif usage_patterns.get('domain_analysis_calls', 0) > 100:
            return "competitive intelligence and market research"
        else:
            return "general SEO optimization"
    
    def _generate_code_example(self, endpoint: str, user: User) -> str:
        """Generate personalized code example for user"""
        return f"""
# Example usage for {endpoint}
import linkprofiler

client = linkprofiler.Client(api_key="your_api_key")
result = await client.{endpoint.split('/')[-1]}("example.com", source="cache")
print(result)
"""
    
    async def _get_performance_metrics(self) -> Dict[str, Dict[str, float]]:
        """Get current performance metrics for all endpoints"""
        # This would integrate with your monitoring system (Prometheus, etc.)
        return {
            "/api/domains/overview": {
                "avg_response_time_ms": 450,
                "error_rate": 0.02,
                "requests_per_minute": 150
            },
            "/api/domains/backlinks": {
                "avg_response_time_ms": 380,
                "error_rate": 0.01,
                "requests_per_minute": 200
            }
        }
    
    async def _trigger_performance_alert(self, endpoint: str, description: str, metrics: Dict[str, Any]):
        """Trigger automated performance alert"""
        affected_users = await self._get_users_using_endpoints([endpoint])
        
        for user in affected_users:
            context = {
                "affected_endpoint": endpoint,
                "start_time": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
                "impact_description": description,
                "resolution_description": "Our team is investigating and will provide updates",
                "service_credit": 0,  # Calculate based on impact
                "affected_requests": await self._count_user_requests_to_endpoints(user.id, [endpoint])
            }
            
            await self.communication_service.send_notification(
                user,
                APIEventType.PERFORMANCE_ISSUE,
                context
            )
    
    async def _get_user_quota_status(self, user_id: str) -> Dict[str, Dict[str, Any]]:
        """Get quota status for user"""
        # This would integrate with your quota tracking system
        return {
            "live_api_calls": {
                "used": 150,
                "limit": 1000,
                "percentage_used": 15,
                "reset_date": "2025-02-01"
            }
        }
    
    async def _get_due_notifications(self) -> List[APIChangeNotification]:
        """Get notifications that are due to be sent"""
        now = datetime.utcnow().timestamp()
        
        if self.redis_client:
            # Get notifications due before now
            due_ids = await self.redis_client.zrangebyscore(
                "scheduled_notifications", 
                0, 
                now
            )
            
            notifications = []
            for notif_id in due_ids:
                data = await self.redis_client.hget(f"api_notifications:{notif_id}", "data")
                if data:
                    notif_dict = json.loads(data)
                    notifications.append(APIChangeNotification(**notif_dict))
            
            return notifications
        
        return []
    
    async def _send_scheduled_notification(self, notification: APIChangeNotification):
        """Send a scheduled notification"""
        target_users = await self._get_users_by_tier(notification.target_users)
        
        for user in target_users:
            context = {
                "affected_endpoints": ", ".join(notification.affected_endpoints),
                "scheduled_date": notification.scheduled_date.strftime("%B %d, %Y"),
                "description": notification.description,
                "migration_guide_url": notification.metadata.get("migration_guide_url", ""),
                "support_url": "https://support.linkprofiler.com"
            }
            
            await self.communication_service.send_notification(
                user,
                notification.event_type,
                context
            )
        
        # Mark as sent
        if self.redis_client:
            await self.redis_client.zrem("scheduled_notifications", notification.id)
            await self.redis_client.hset(f"api_notifications:{notification.id}", "status", "sent")

# Global singleton
api_notification_triggers = None

async def get_api_notification_triggers(
    db: Database, 
    communication_service: APICommunicationService, 
    redis_client=None
) -> APINotificationTriggers:
    """Get or create the global API notification triggers instance"""
    global api_notification_triggers
    if api_notification_triggers is None:
        api_notification_triggers = APINotificationTriggers(db, communication_service, redis_client)
        await api_notification_triggers.start_automated_monitoring()
    return api_notification_triggers