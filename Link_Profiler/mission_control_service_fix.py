# At the end of the file, replace the singleton pattern with proper initialization
mission_control_service: Optional['MissionControlService'] = None

def initialize_mission_control_service(redis_client, smart_crawl_queue, api_quota_manager, dashboard_alert_service):
    """Initialize the global mission control service instance."""
    global mission_control_service
    mission_control_service = MissionControlService(
        redis_client=redis_client,
        smart_crawl_queue=smart_crawl_queue,
        api_quota_manager=api_quota_manager,
        dashboard_alert_service=dashboard_alert_service
    )
    return mission_control_service

def get_mission_control_service():
    """Get the global mission control service instance."""
    return mission_control_service
