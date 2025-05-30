#!/usr/bin/env python3
"""
Standalone Job Coordinator Entry Point
"""
import sys
import os
import asyncio
import logging

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from Link_Profiler.queue_system.job_coordinator import JobCoordinator

def main():
    """Main entry point for job coordinator"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Link Profiler Job Coordinator")
    parser.add_argument("--redis-url", default="redis://localhost:6379", 
                       help="Redis connection URL")
    parser.add_argument("--log-level", default="INFO", 
                       help="Logging level")
    
    args = parser.parse_args()
    
    # Configure logging
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print(f"""
🎯 Starting Link Profiler Job Coordinator
   Redis: {args.redis_url}
   Log Level: {args.log_level}
""")
    
    async def run_coordinator():
        async with JobCoordinator(redis_url=args.redis_url) as coordinator:
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
    
    try:
        asyncio.run(run_coordinator())
    except KeyboardInterrupt:
        print("\n🛑 Coordinator stopped")
    except Exception as e:
        print(f"❌ Coordinator failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
