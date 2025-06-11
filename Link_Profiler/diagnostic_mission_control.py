#!/usr/bin/env python3
"""
Mission Control Diagnostic Script
Diagnoses issues with Mission Control WebSocket connectivity

Run this script from the Link_Profiler directory:
python diagnostic_mission_control.py
"""

import sys
import os
import asyncio
import logging

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from Link_Profiler.config.config_loader import config_loader
from Link_Profiler.services.mission_control_service import mission_control_service

# Setup basic logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def diagnose_mission_control():
    """Diagnose Mission Control service and WebSocket configuration"""
    
    print("=" * 50)
    print("MISSION CONTROL DIAGNOSTIC REPORT")
    print("=" * 50)
    
    # Check 1: Configuration values
    print("\n1. CONFIGURATION CHECK:")
    print("-" * 30)
    
    mission_control_enabled = config_loader.get("mission_control.enabled", False)
    websocket_enabled = config_loader.get("mission_control.websocket_enabled", False)
    dashboard_refresh_rate = config_loader.get("mission_control.dashboard_refresh_rate", 1000)
    max_websocket_connections = config_loader.get("mission_control.max_websocket_connections", 100)
    cache_ttl = config_loader.get("mission_control.cache_ttl", 60)
    
    print(f"[OK] mission_control.enabled: {mission_control_enabled}")
    print(f"[OK] mission_control.websocket_enabled: {websocket_enabled}")
    print(f"[OK] mission_control.dashboard_refresh_rate: {dashboard_refresh_rate}")
    print(f"[OK] mission_control.max_websocket_connections: {max_websocket_connections}")
    print(f"[OK] mission_control.cache_ttl: {cache_ttl}")
    
    # Check 2: Environment Variables
    print("\n2. ENVIRONMENT VARIABLES CHECK:")
    print("-" * 30)
    
    redis_url = os.getenv("LP_REDIS_URL")
    database_url = os.getenv("LP_DATABASE_URL")
    auth_secret_key = os.getenv("LP_AUTH_SECRET_KEY")
    
    print(f"[OK] LP_REDIS_URL: {'SET' if redis_url else 'NOT SET'}")
    print(f"[OK] LP_DATABASE_URL: {'SET' if database_url else 'NOT SET'}")
    print(f"[OK] LP_AUTH_SECRET_KEY: {'SET' if auth_secret_key else 'NOT SET'}")
    
    if redis_url:
        print(f"  Redis URL: {redis_url[:20]}...")
    if database_url:
        print(f"  Database URL: {database_url[:20]}...")
    
    # Check 3: Mission Control Service Status
    print("\n3. MISSION CONTROL SERVICE CHECK:")
    print("-" * 30)
    
    print(f"[OK] mission_control_service object: {mission_control_service}")
    print(f"[OK] mission_control_service type: {type(mission_control_service)}")
    
    if mission_control_service:
        print(f"[OK] websocket_enabled attribute: {hasattr(mission_control_service, 'websocket_enabled')}")
        if hasattr(mission_control_service, 'websocket_enabled'):
            print(f"[OK] websocket_enabled value: {mission_control_service.websocket_enabled}")
        
        print(f"[OK] max_websocket_connections attribute: {hasattr(mission_control_service, 'max_websocket_connections')}")
        if hasattr(mission_control_service, 'max_websocket_connections'):
            print(f"[OK] max_websocket_connections value: {mission_control_service.max_websocket_connections}")
        
        print(f"[OK] redis attribute: {hasattr(mission_control_service, 'redis')}")
        if hasattr(mission_control_service, 'redis'):
            print(f"[OK] redis client: {mission_control_service.redis}")
        
        print(f"[OK] dashboard_refresh_rate_seconds attribute: {hasattr(mission_control_service, 'dashboard_refresh_rate_seconds')}")
        if hasattr(mission_control_service, 'dashboard_refresh_rate_seconds'):
            print(f"[OK] dashboard_refresh_rate_seconds value: {mission_control_service.dashboard_refresh_rate_seconds}")
    else:
        print("[ERROR] mission_control_service is None!")
    
    # Check 4: Try to test the WebSocket endpoint check logic
    print("\n4. WEBSOCKET ENDPOINT LOGIC TEST:")
    print("-" * 30)
    
    # Simulate the logic from the WebSocket endpoint
    if not mission_control_service:
        print("[ERROR] Mission Control service is None! Service not initialized properly.")
        return
        
    if not hasattr(mission_control_service, 'websocket_enabled'):
        print("[ERROR] Mission Control service missing websocket_enabled attribute!")
        return
        
    if not mission_control_service.websocket_enabled:
        print(f"[ERROR] Mission Control WebSocket is disabled. websocket_enabled={mission_control_service.websocket_enabled}")
        return
    
    print("[SUCCESS] All WebSocket endpoint checks would pass!")
    
    # Check 5: Try to create a Redis connection
    print("\n5. REDIS CONNECTION TEST:")
    print("-" * 30)
    
    try:
        import redis.asyncio as redis
        redis_url_config = config_loader.get("redis.url", "redis://localhost:6379/0")
        print(f"[OK] Using Redis URL: {redis_url_config}")
        
        redis_client = redis.from_url(redis_url_config)
        await redis_client.ping()
        print("[SUCCESS] Redis connection successful!")
        await redis_client.close()
    except Exception as e:
        print(f"[ERROR] Redis connection failed: {e}")
    
    # Check 6: Database connection
    print("\n6. DATABASE CONNECTION TEST:")
    print("-" * 30)
    
    try:
        from Link_Profiler.database.database import db
        db_status = db.ping()
        print(f"[SUCCESS] Database connection: {db_status}")
    except Exception as e:
        print(f"[ERROR] Database connection failed: {e}")
    
    print("\n" + "=" * 50)
    print("DIAGNOSTIC COMPLETE")
    print("=" * 50)

if __name__ == "__main__":
    asyncio.run(diagnose_mission_control())
