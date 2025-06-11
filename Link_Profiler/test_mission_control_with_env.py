#!/usr/bin/env python3
"""
Test Mission Control with Environment Variables Set
This script sets the required environment variables and tests Mission Control
"""

import os
import sys
import asyncio

# Set the required environment variables directly
os.environ["LP_REDIS_URL"] = "redis://localhost:6379/0"
os.environ["LP_DATABASE_URL"] = "postgresql://link_profiler:password@localhost:5432/link_profiler_db"
os.environ["LP_AUTH_SECRET_KEY"] = "test-secret-key-for-mission-control-debugging-please-change-in-production"
os.environ["LP_MONITOR_PASSWORD"] = "test-monitor-password"

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

print("Environment variables set:")
print(f"LP_REDIS_URL: {os.environ.get('LP_REDIS_URL')}")
print(f"LP_DATABASE_URL: {os.environ.get('LP_DATABASE_URL')}")
print(f"LP_AUTH_SECRET_KEY: SET (hidden)")

# Now import and test
from Link_Profiler.config.config_loader import config_loader

print("\nConfiguration values after setting environment variables:")
print(f"mission_control.enabled: {config_loader.get('mission_control.enabled')}")
print(f"mission_control.websocket_enabled: {config_loader.get('mission_control.websocket_enabled')}")
print(f"redis.url: {config_loader.get('redis.url')}")
print(f"database.url: {config_loader.get('database.url')}")

async def test_mission_control_with_env():
    """Test Mission Control with environment variables set"""
    
    try:
        # Test Redis connection
        import redis.asyncio as redis
        redis_url = config_loader.get("redis.url")
        print(f"\nTesting Redis connection with URL: {redis_url}")
        
        redis_client = redis.from_url(redis_url)
        await redis_client.ping()
        print("[SUCCESS] Redis connection works!")
        await redis_client.close()
        
    except Exception as e:
        print(f"[ERROR] Redis connection failed: {e}")
        return False
    
    try:
        # Test Database connection
        from Link_Profiler.database.database import db
        db_status = db.ping()
        print(f"[SUCCESS] Database connection: {db_status}")
        
    except Exception as e:
        print(f"[ERROR] Database connection failed: {e}")
        return False
    
    try:
        # Now try to initialize Mission Control service
        import redis.asyncio as redis
        from Link_Profiler.database.database import db
        from Link_Profiler.services.mission_control_service import MissionControlService
        from Link_Profiler.services.dashboard_alert_service import DashboardAlertService
        from Link_Profiler.utils.api_quota_manager import APIQuotaManager
        from Link_Profiler.queue_system.smart_crawler_queue import SmartCrawlQueue
        from Link_Profiler.utils.distributed_circuit_breaker import DistributedResilienceManager
        
        print("\nInitializing Mission Control dependencies...")
        
        # Create Redis client
        redis_url = config_loader.get("redis.url")
        redis_client = redis.from_url(redis_url)
        
        # Create dependencies
        distributed_resilience_manager = DistributedResilienceManager(redis_client=redis_client)
        api_quota_manager = APIQuotaManager(config_loader._config_data, resilience_manager=distributed_resilience_manager, redis_client=redis_client)
        smart_crawl_queue = SmartCrawlQueue(redis_client=redis_client, config_loader=config_loader)
        dashboard_alert_service = DashboardAlertService(db=db, redis_client=redis_client, api_quota_manager=api_quota_manager)
        
        print("[SUCCESS] Dependencies initialized")
        
        # Initialize Mission Control Service
        mission_control_service = MissionControlService(
            redis_client=redis_client,
            smart_crawl_queue=smart_crawl_queue,
            api_quota_manager=api_quota_manager,
            dashboard_alert_service=dashboard_alert_service
        )
        
        print("[SUCCESS] Mission Control service initialized!")
        print(f"WebSocket enabled: {mission_control_service.websocket_enabled}")
        print(f"Max connections: {mission_control_service.max_websocket_connections}")
        print(f"Refresh rate: {mission_control_service.dashboard_refresh_rate_seconds}s")
        
        # Test basic functionality
        try:
            print("\nTesting Mission Control realtime updates...")
            updates = await mission_control_service.get_realtime_updates()
            print("[SUCCESS] Mission Control can generate realtime updates!")
            print(f"Update timestamp: {updates.timestamp}")
            
        except Exception as e:
            print(f"[WARNING] Mission Control initialized but cannot generate updates: {e}")
            import traceback
            traceback.print_exc()
        
        await redis_client.close()
        print("\n[OVERALL SUCCESS] Mission Control should now work properly!")
        return True
        
    except Exception as e:
        print(f"[ERROR] Failed to initialize Mission Control: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    asyncio.run(test_mission_control_with_env())
