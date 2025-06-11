#!/usr/bin/env python3
"""
Startup Check Script - Verifies all components are working properly
Run this after uploading the fixes to test the system.
"""

import sys
import os
import asyncio
import logging
from datetime import datetime

# Add the Link_Profiler directory to sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'Link_Profiler'))

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_startup_components():
    """Test all critical startup components"""
    print("🚀 Link Profiler Startup Check")
    print("=" * 50)
    
    success_count = 0
    total_tests = 8
    
    # Test 1: Environment Loading
    print("\n1. Testing Environment Loading...")
    try:
        from Link_Profiler.config import env_loader  # This should auto-load .env
        from Link_Profiler.config.config_loader import config_loader
        
        # Test that env vars are loaded
        test_value = config_loader.get("LP_MONITOR_PASSWORD")
        if test_value:
            print("   ✅ Environment variables loaded successfully")
            success_count += 1
        else:
            print("   ❌ Environment variables not loaded properly")
    except Exception as e:
        print(f"   ❌ Environment loading failed: {e}")
    
    # Test 2: Database Connection
    print("\n2. Testing Database Connection...")
    try:
        from Link_Profiler.database.database import db
        
        # Test basic database connection
        result = db.get_session().execute(db.text("SELECT 1")).fetchone()
        if result:
            print("   ✅ Database connection successful")
            success_count += 1
        else:
            print("   ❌ Database connection failed")
    except Exception as e:
        print(f"   ❌ Database connection error: {e}")
    
    # Test 3: Database Schema
    print("\n3. Testing Database Schema...")
    try:
        from Link_Profiler.database.database import db
        
        # Check if required columns exist
        columns_check = db.get_session().execute(
            db.text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'crawl_jobs' 
                AND column_name IN ('errors', 'created_at', 'config')
            """)
        ).fetchall()
        
        if len(columns_check) >= 3:
            print("   ✅ Database schema has required columns")
            success_count += 1
        else:
            print(f"   ❌ Missing columns in crawl_jobs table. Found: {[c[0] for c in columns_check]}")
    except Exception as e:
        print(f"   ❌ Database schema check error: {e}")
    
    # Test 4: Redis Connection
    print("\n4. Testing Redis Connection...")
    try:
        import redis.asyncio as redis
        from Link_Profiler.config.config_loader import config_loader
        
        redis_url = config_loader.get("redis.url", "redis://localhost:6379/0")
        redis_client = redis.from_url(redis_url)
        
        result = await redis_client.ping()
        if result:
            print("   ✅ Redis connection successful")
            success_count += 1
        else:
            print("   ❌ Redis ping failed")
        await redis_client.close()
    except Exception as e:
        print(f"   ❌ Redis connection error: {e}")
    
    # Test 5: Job Coordinator
    print("\n5. Testing Job Coordinator...")
    try:
        from Link_Profiler.queue_system.job_coordinator import get_coordinator
        
        coordinator = get_coordinator()  # Should not be awaited
        if coordinator:
            status = coordinator.get_status() if hasattr(coordinator, 'get_status') else {}
            print(f"   ✅ Job Coordinator created successfully. Status: {status.get('status', 'unknown')}")
            success_count += 1
        else:
            print("   ❌ Job Coordinator creation failed")
    except Exception as e:
        print(f"   ❌ Job Coordinator error: {e}")
    
    # Test 6: Mission Control Service
    print("\n6. Testing Mission Control Service...")
    try:
        from Link_Profiler.services.mission_control_service import MissionControlService
        import redis.asyncio as redis
        from Link_Profiler.config.config_loader import config_loader
        
        redis_url = config_loader.get("redis.url", "redis://localhost:6379/0")
        redis_client = redis.from_url(redis_url)
        
        # Create mission control service
        service = MissionControlService(redis_client=redis_client)
        if service:
            print("   ✅ Mission Control Service created successfully")
            success_count += 1
        else:
            print("   ❌ Mission Control Service creation failed")
        await redis_client.close()
    except Exception as e:
        print(f"   ❌ Mission Control Service error: {e}")
    
    # Test 7: Authentication
    print("\n7. Testing Authentication...")
    try:
        from Link_Profiler.auth.auth import authenticate_user
        
        # Test the monitor user authentication
        test_username = "monitor_user"
        test_password = "secure_monitor_password_123"
        
        user = authenticate_user(test_username, test_password)
        if user:
            print(f"   ✅ Authentication successful for user: {user.username}")
            success_count += 1
        else:
            print("   ❌ Authentication failed for monitor user")
    except Exception as e:
        print(f"   ❌ Authentication error: {e}")
    
    # Test 8: WebSocket Endpoint
    print("\n8. Testing WebSocket Components...")
    try:
        from Link_Profiler.utils.connection_manager import ConnectionManager
        
        connection_manager = ConnectionManager()
        if connection_manager:
            print("   ✅ Connection Manager created successfully")
            success_count += 1
        else:
            print("   ❌ Connection Manager creation failed")
    except Exception as e:
        print(f"   ❌ WebSocket components error: {e}")
    
    # Summary
    print("\n" + "=" * 50)
    print(f"📊 STARTUP CHECK SUMMARY")
    print(f"✅ Passed: {success_count}/{total_tests}")
    print(f"❌ Failed: {total_tests - success_count}/{total_tests}")
    
    if success_count == total_tests:
        print("\n🎉 ALL TESTS PASSED! System is ready for operation.")
        return True
    else:
        print(f"\n⚠️  {total_tests - success_count} tests failed. Please fix before deploying.")
        return False

def main():
    """Main function to run the startup check"""
    try:
        result = asyncio.run(test_startup_components())
        if result:
            print("\n🚀 You can now start the service with:")
            print("   sudo systemctl restart linkprofiler-api.service")
            print("   sudo systemctl status linkprofiler-api.service")
            sys.exit(0)
        else:
            print("\n🔧 Fix the issues above before starting the service.")
            sys.exit(1)
    except Exception as e:
        print(f"\n💥 Critical error during startup check: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
