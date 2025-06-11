# Link_Profiler/api/admin_communication.py
"""
Admin endpoints for managing API communications and notifications
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Body, Query
from pydantic import BaseModel, Field

from Link_Profiler.core.models import User
from Link_Profiler.api.dependencies import get_current_admin_user
from Link_Profiler.services.api_notification_triggers import get_api_notification_triggers, APIChangeNotification
from Link_Profiler.services.api_communication_service import get_api_communication_service

logger = logging.getLogger(__name__)

# Pydantic Models for API Communication Management
class ScheduleDeprecationRequest(BaseModel):
    deprecated_endpoints: List[str] = Field(..., description="List of endpoints being deprecated")
    deprecation_date: datetime = Field(..., description="When endpoints will be deprecated")
    replacement_info: Dict[str, str] = Field(..., description="Mapping of old endpoint -> new endpoint")
    advance_notice_days: int = Field(30, description="Days in advance to notify users")
    migration_guide_content: Optional[str] = Field(None, description="Custom migration guide content")

class ScheduleMaintenanceRequest(BaseModel):
    maintenance_start: datetime = Field(..., description="Maintenance window start time")
    maintenance_end: datetime = Field(..., description="Maintenance window end time") 
    affected_services: List[str] = Field(..., description="List of affected services/endpoints")
    impact_description: str = Field(..., description="Description of the maintenance impact")
    advance_notice_hours: int = Field(24, description="Hours in advance to notify users")

class PerformanceAlertRequest(BaseModel):
    affected_endpoints: List[str] = Field(..., description="Endpoints experiencing issues")
    issue_description: str = Field(..., description="Description of the performance issue")
    resolution_eta: Optional[datetime] = Field(None, description="Expected resolution time")
    service_credit: Optional[float] = Field(None, description="Service credit amount ($)")
    affected_user_count: Optional[int] = Field(None, description="Estimated number of affected users")

class NewFeatureAnnouncementRequest(BaseModel):
    feature_name: str = Field(..., description="Name of the new feature")
    new_endpoints: List[str] = Field(..., description="New endpoints being introduced")
    feature_description: str = Field(..., description="Detailed description of the feature")
    target_user_tier: str = Field("all", description="Target user tier: all, basic+, pro+, enterprise")
    launch_date: Optional[datetime] = Field(None, description="Feature launch date")
    documentation_url: Optional[str] = Field(None, description="Link to feature documentation")

class NotificationResponse(BaseModel):
    notification_id: str
    status: str
    scheduled_for: datetime
    target_user_count: int
    message: str

class NotificationStatusResponse(BaseModel):
    id: str
    event_type: str
    title: str
    status: str
    created_at: datetime
    scheduled_date: datetime
    notification_date: datetime
    target_users: str
    affected_endpoints: List[str]
    sent_count: Optional[int] = None
    delivery_rate: Optional[float] = None

# Router for admin communication endpoints
admin_communication_router = APIRouter(
    prefix="/api/admin/communications",
    tags=["Admin - API Communications"],
    dependencies=[Depends(get_current_admin_user)]
)

@admin_communication_router.post("/deprecation/schedule", response_model=NotificationResponse)
async def schedule_api_deprecation(
    request: ScheduleDeprecationRequest,
    current_admin: User = Depends(get_current_admin_user)
):
    """
    Schedule an API deprecation notice to be sent to all users.
    
    **Access:** Admin only
    **Use Case:** When deprecating API endpoints, schedule advance notice to users
    """
    try:
        # Get services
        notification_triggers = await get_api_notification_triggers()
        
        # Schedule the deprecation notice
        notification_id = await notification_triggers.schedule_api_deprecation_notice(
            admin_user=current_admin,
            deprecated_endpoints=request.deprecated_endpoints,
            deprecation_date=request.deprecation_date,
            replacement_info=request.replacement_info,
            advance_notice_days=request.advance_notice_days
        )
        
        # Calculate target user count
        all_users = notification_triggers.db.get_all_users()
        target_count = len([u for u in all_users if u.is_active])
        
        notification_date = request.deprecation_date - timedelta(days=request.advance_notice_days)
        
        return NotificationResponse(
            notification_id=notification_id,
            status="scheduled",
            scheduled_for=notification_date,
            target_user_count=target_count,
            message=f"Deprecation notice scheduled for {len(request.deprecated_endpoints)} endpoints"
        )
        
    except Exception as e:
        logger.error(f"Error scheduling deprecation notice: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to schedule deprecation notice: {str(e)}"
        )

@admin_communication_router.post("/maintenance/schedule", response_model=NotificationResponse)
async def schedule_maintenance_notification(
    request: ScheduleMaintenanceRequest,
    current_admin: User = Depends(get_current_admin_user)
):
    """
    Schedule a maintenance window notification.
    
    **Access:** Admin only
    **Use Case:** Notify users of planned maintenance that may affect API availability
    """
    try:
        notification_triggers = await get_api_notification_triggers()
        
        notification_id = await notification_triggers.schedule_maintenance_notice(
            admin_user=current_admin,
            maintenance_start=request.maintenance_start,
            maintenance_end=request.maintenance_end,
            affected_services=request.affected_services,
            impact_description=request.impact_description,
            advance_notice_hours=request.advance_notice_hours
        )
        
        all_users = notification_triggers.db.get_all_users()
        target_count = len([u for u in all_users if u.is_active])
        
        notification_date = request.maintenance_start - timedelta(hours=request.advance_notice_hours)
        
        return NotificationResponse(
            notification_id=notification_id,
            status="scheduled", 
            scheduled_for=notification_date,
            target_user_count=target_count,
            message=f"Maintenance notice scheduled for {len(request.affected_services)} services"
        )
        
    except Exception as e:
        logger.error(f"Error scheduling maintenance notice: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to schedule maintenance notice: {str(e)}"
        )

@admin_communication_router.post("/performance/alert", response_model=NotificationResponse)
async def send_performance_alert(
    request: PerformanceAlertRequest,
    current_admin: User = Depends(get_current_admin_user)
):
    """
    Send immediate performance issue alert to affected users.
    
    **Access:** Admin only
    **Use Case:** Notify users immediately when performance issues are detected
    """
    try:
        notification_triggers = await get_api_notification_triggers()
        
        notification_id = await notification_triggers.send_immediate_performance_alert(
            admin_user=current_admin,
            affected_endpoints=request.affected_endpoints,
            issue_description=request.issue_description,
            resolution_eta=request.resolution_eta,
            service_credit=request.service_credit
        )
        
        # Estimate affected users based on endpoint usage
        affected_users = await notification_triggers._get_users_using_endpoints(request.affected_endpoints)
        
        return NotificationResponse(
            notification_id=notification_id,
            status="sent",
            scheduled_for=datetime.utcnow(),
            target_user_count=len(affected_users),
            message=f"Performance alert sent for {len(request.affected_endpoints)} endpoints"
        )
        
    except Exception as e:
        logger.error(f"Error sending performance alert: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send performance alert: {str(e)}"
        )

@admin_communication_router.post("/features/announce", response_model=NotificationResponse)
async def announce_new_feature(
    request: NewFeatureAnnouncementRequest,
    current_admin: User = Depends(get_current_admin_user)
):
    """
    Announce a new API feature to users.
    
    **Access:** Admin only
    **Use Case:** Notify users about new features that might benefit their use cases
    """
    try:
        notification_triggers = await get_api_notification_triggers()
        
        notification_id = await notification_triggers.announce_new_feature(
            admin_user=current_admin,
            feature_name=request.feature_name,
            new_endpoints=request.new_endpoints,
            feature_description=request.feature_description,
            target_user_tier=request.target_user_tier
        )
        
        # Calculate target user count based on tier
        target_users = await notification_triggers._get_users_by_tier(request.target_user_tier)
        
        return NotificationResponse(
            notification_id=notification_id,
            status="sent",
            scheduled_for=datetime.utcnow(),
            target_user_count=len(target_users),
            message=f"Feature announcement sent to {request.target_user_tier} tier users"
        )
        
    except Exception as e:
        logger.error(f"Error announcing new feature: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to announce new feature: {str(e)}"
        )

@admin_communication_router.get("/notifications", response_model=List[NotificationStatusResponse])
async def list_scheduled_notifications(
    status_filter: Optional[str] = Query(None, description="Filter by status: draft, scheduled, sent, cancelled"),
    event_type_filter: Optional[str] = Query(None, description="Filter by event type"),
    limit: int = Query(50, description="Maximum number of notifications to return"),
    current_admin: User = Depends(get_current_admin_user)
):
    """
    List all scheduled and sent notifications.
    
    **Access:** Admin only
    **Use Case:** View history and status of all API communications
    """
    try:
        notification_triggers = await get_api_notification_triggers()
        
        # Get notifications from storage (this would be implemented in the triggers service)
        notifications = await notification_triggers._get_all_notifications(
            status_filter=status_filter,
            event_type_filter=event_type_filter,
            limit=limit
        )
        
        response = []
        for notification in notifications:
            # Calculate delivery metrics if sent
            sent_count = None
            delivery_rate = None
            if notification.status == "sent":
                sent_count = await notification_triggers._get_notification_delivery_count(notification.id)
                target_count = await notification_triggers._get_notification_target_count(notification.id)
                delivery_rate = (sent_count / target_count) if target_count > 0 else 0
            
            response.append(NotificationStatusResponse(
                id=notification.id,
                event_type=notification.event_type.value,
                title=notification.title,
                status=notification.status,
                created_at=notification.created_at,
                scheduled_date=notification.scheduled_date,
                notification_date=notification.notification_date,
                target_users=notification.target_users,
                affected_endpoints=notification.affected_endpoints,
                sent_count=sent_count,
                delivery_rate=delivery_rate
            ))
        
        return response
        
    except Exception as e:
        logger.error(f"Error listing notifications: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list notifications: {str(e)}"
        )

@admin_communication_router.get("/notifications/{notification_id}", response_model=NotificationStatusResponse)
async def get_notification_status(
    notification_id: str,
    current_admin: User = Depends(get_current_admin_user)
):
    """
    Get detailed status of a specific notification.
    
    **Access:** Admin only
    **Use Case:** Check delivery status and metrics for a specific notification
    """
    try:
        notification_triggers = await get_api_notification_triggers()
        
        notification = await notification_triggers._get_notification_by_id(notification_id)
        if not notification:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Notification not found"
            )
        
        # Get delivery metrics
        sent_count = await notification_triggers._get_notification_delivery_count(notification_id)
        target_count = await notification_triggers._get_notification_target_count(notification_id)
        delivery_rate = (sent_count / target_count) if target_count > 0 else 0
        
        return NotificationStatusResponse(
            id=notification.id,
            event_type=notification.event_type.value,
            title=notification.title,
            status=notification.status,
            created_at=notification.created_at,
            scheduled_date=notification.scheduled_date,
            notification_date=notification.notification_date,
            target_users=notification.target_users,
            affected_endpoints=notification.affected_endpoints,
            sent_count=sent_count,
            delivery_rate=delivery_rate
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting notification status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get notification status: {str(e)}"
        )

@admin_communication_router.delete("/notifications/{notification_id}")
async def cancel_scheduled_notification(
    notification_id: str,
    current_admin: User = Depends(get_current_admin_user)
):
    """
    Cancel a scheduled notification before it's sent.
    
    **Access:** Admin only
    **Use Case:** Cancel notifications that are no longer needed
    """
    try:
        notification_triggers = await get_api_notification_triggers()
        
        success = await notification_triggers._cancel_notification(notification_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Notification not found or cannot be cancelled"
            )
        
        return {"message": f"Notification {notification_id} cancelled successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling notification: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel notification: {str(e)}"
        )

@admin_communication_router.post("/test/send")
async def send_test_notification(
    test_user_email: str = Body(..., description="Email address to send test notification to"),
    event_type: str = Body(..., description="Type of notification to test"),
    current_admin: User = Depends(get_current_admin_user)
):
    """
    Send a test notification to verify email templates and delivery.
    
    **Access:** Admin only
    **Use Case:** Test notification templates before sending to all users
    """
    try:
        communication_service = await get_api_communication_service()
        
        # Create a test user object
        test_user = User(
            id="test_user",
            username="Test User",
            email=test_user_email,
            hashed_password="",
            is_active=True
        )
        
        # Prepare test context based on event type
        test_contexts = {
            "quota_warning": {
                "api_name": "Domain Analysis API",
                "percentage_used": 85,
                "used_calls": 850,
                "remaining_calls": 150,
                "reset_date": "February 1, 2025",
                "next_tier": "Pro",
                "next_tier_quota": 10000,
                "upgrade_url": "https://billing.linkprofiler.com/upgrade"
            },
            "new_feature": {
                "feature_name": "AI-Powered Link Prospects",
                "use_case": "link building and outreach",
                "new_endpoint": "/api/domains/{domain}/link-prospects",
                "feature_description": "Automatically identify high-quality link building opportunities",
                "performance_benefit": "60% faster prospect identification",
                "pricing_info": "Included in Pro and Enterprise plans",
                "code_example": "result = client.domains.get_link_prospects('example.com')",
                "docs_url": "https://docs.linkprofiler.com/features/link-prospects"
            },
            "performance_issue": {
                "affected_endpoint": "/api/domains/backlinks",
                "start_time": "2025-01-15 14:30 UTC",
                "end_time": "2025-01-15 14:45 UTC",
                "impact_description": "Increased response times due to database optimization",
                "affected_requests": 127,
                "resolution_description": "Database optimization completed, performance restored",
                "service_credit": 15,
                "prevention_measure_1": "Enhanced database monitoring implemented",
                "prevention_measure_2": "Auto-scaling thresholds optimized",
                "prevention_measure_3": "Circuit breaker patterns improved"
            }
        }
        
        context = test_contexts.get(event_type, {
            "test_message": "This is a test notification",
            "timestamp": datetime.utcnow().isoformat()
        })
        
        # Send the test notification
        from Link_Profiler.services.api_communication_service import APIEventType
        event_enum = getattr(APIEventType, event_type.upper(), APIEventType.NEW_FEATURE)
        
        success = await communication_service.send_notification(
            test_user,
            event_enum,
            context
        )
        
        return {
            "message": f"Test notification sent to {test_user_email}",
            "success": success,
            "event_type": event_type,
            "context_used": context
        }
        
    except Exception as e:
        logger.error(f"Error sending test notification: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send test notification: {str(e)}"
        )

@admin_communication_router.get("/analytics/delivery-metrics")
async def get_communication_analytics(
    days: int = Query(30, description="Number of days to analyze"),
    current_admin: User = Depends(get_current_admin_user)
):
    """
    Get analytics on notification delivery rates and user engagement.
    
    **Access:** Admin only
    **Use Case:** Monitor effectiveness of API communications
    """
    try:
        notification_triggers = await get_api_notification_triggers()
        
        # Get analytics data (this would be implemented in the triggers service)
        analytics = await notification_triggers._get_communication_analytics(days)
        
        return {
            "period_days": days,
            "total_notifications_sent": analytics.get("total_sent", 0),
            "delivery_rate": analytics.get("delivery_rate", 0),
            "open_rate": analytics.get("open_rate", 0),
            "click_through_rate": analytics.get("click_through_rate", 0),
            "unsubscribe_rate": analytics.get("unsubscribe_rate", 0),
            "notifications_by_type": analytics.get("by_type", {}),
            "user_engagement_score": analytics.get("engagement_score", 0),
            "top_performing_templates": analytics.get("top_templates", []),
            "improvement_suggestions": analytics.get("suggestions", [])
        }
        
    except Exception as e:
        logger.error(f"Error getting communication analytics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get communication analytics: {str(e)}"
        )

@admin_communication_router.post("/templates/preview")
async def preview_notification_template(
    event_type: str = Body(..., description="Event type to preview"),
    custom_context: Dict[str, Any] = Body({}, description="Custom context for template preview"),
    current_admin: User = Depends(get_current_admin_user)
):
    """
    Preview how a notification template will look with sample or custom data.
    
    **Access:** Admin only
    **Use Case:** Preview templates before sending notifications
    """
    try:
        communication_service = await get_api_communication_service()
        
        # Get the template for the event type
        from Link_Profiler.services.api_communication_service import APIEventType
        event_enum = getattr(APIEventType, event_type.upper(), APIEventType.NEW_FEATURE)
        
        template = communication_service.templates.get(event_enum)
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Template not found for event type: {event_type}"
            )
        
        # Use custom context or generate sample context
        if not custom_context:
            custom_context = {
                "customer_name": "John Doe",
                "api_name": "Domain Analysis API",
                "current_tier": "Pro",
                "support_url": "https://support.linkprofiler.com",
                "upgrade_url": "https://billing.linkprofiler.com/upgrade"
            }
        
        # Render template with context
        rendered_subject = template.subject_template.format(**custom_context)
        rendered_email = template.email_template.format(**custom_context)
        rendered_in_app = template.in_app_template.format(**custom_context)
        
        return {
            "event_type": event_type,
            "template_info": {
                "priority": template.priority.value,
                "channels": [c.value for c in template.channels]
            },
            "rendered_content": {
                "subject": rendered_subject,
                "email_html": rendered_email,
                "in_app_message": rendered_in_app
            },
            "context_used": custom_context,
            "personalization_fields": template.personalization_fields
        }
        
    except Exception as e:
        logger.error(f"Error previewing template: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to preview template: {str(e)}"
        )