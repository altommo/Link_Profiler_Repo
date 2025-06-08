#!/usr/bin/env python3
"""
Standalone Job Coordinator Entry Point
"""
import sys
import os
import asyncio
import logging
# Add project root to path
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from Link_Profiler.config.config_loader import ConfigLoader
from Link_Profiler.queue_system.job_coordinator import JobCoordinator
from Link_Profiler.database.database import Database
from Link_Profiler.services.alert_service import AlertService
from Link_Profiler.utils.connection_manager import ConnectionManager
import redis.asyncio as redis

def main():
    """Main entry point for job coordinator"""
    import argparse
    parser = argparse.ArgumentParser(description="Link Profiler Job Coordinator")
    parser.add_argument("--log-level", default="INFO",
                       help="Logging level")
    args = parser.parse_args()
    
    # Configure logging
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    async def run_coordinator():
        # Initialize config loader (it auto-loads config in __init__)
        config_loader = ConfigLoader()
        
        # Get configuration
        redis_url = config_loader.get("redis.url")
        database_url = config_loader.get("database.url")
        
        print(f"""
🎯 Starting Link Profiler Job Coordinator
   Redis: {redis_url}
   Database: {database_url[:50]}...
   Log Level: {args.log_level}
""")
        
        try:
            # Initialize database (singleton - no parameters needed)
            db = Database()
            
            # Initialize Redis
            redis_pool = redis.ConnectionPool.from_url(redis_url)
            redis_client = redis.Redis(connection_pool=redis_pool)
            
            # Test Redis connection
            await redis_client.ping()
            print("✅ Redis connection successful")
            
            # Initialize connection manager
            connection_manager = ConnectionManager()
            
            # Initialize alert service
            alert_service = AlertService(db, connection_manager, redis_client, config_loader)
            
            # Initialize JobCoordinator with correct parameters
            coordinator = JobCoordinator(
                redis_client=redis_client,
                config_loader=config_loader,
                database=db,
                alert_service=alert_service,
                connection_manager=connection_manager
            )
            
            async with coordinator:
                # Start monitoring tasks
                result_task = asyncio.create_task(coordinator.process_results())
                monitor_task = asyncio.create_task(coordinator.monitor_satellites())
                print("✅ Job coordinator started successfully")
                print("📊 Monitoring results and satellite health...")
                
                # Keep running until interrupted
                try:
                    await asyncio.gather(result_task, monitor_task)
                except KeyboardInterrupt:
                    print("\n🛑 Coordinator stopped by user")
                    result_task.cancel()
                    monitor_task.cancel()
                    
        except Exception as e:
            print(f"❌ Failed to initialize coordinator: {e}")
            raise
    
    try:
        asyncio.run(run_coordinator())
    except KeyboardInterrupt:
        print("\n🛑 Coordinator stopped")
    except Exception as e:
        print(f"❌ Coordinator failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
