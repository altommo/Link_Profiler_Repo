#!/usr/bin/env python3
"""
Standalone Satellite Crawler Entry Point
This can be deployed independently to satellite servers
"""
import sys
import os
import asyncio
import logging

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from Link_Profiler.queue_system.satellite_crawler import SatelliteCrawler

def main():
    """Main entry point for satellite crawler"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Link Profiler Satellite Crawler")
    parser.add_argument("--redis-url", default="redis://localhost:6379", 
                       help="Redis connection URL")
    parser.add_argument("--crawler-id", 
                       help="Unique crawler identifier")
    parser.add_argument("--region", default="default", 
                       help="Crawler region/zone")
    parser.add_argument("--log-level", default="INFO", 
                       help="Logging level")
    
    args = parser.parse_args()
    
    # Configure logging
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print(f"""
🛰️ Starting Link Profiler Satellite Crawler
   ID: {args.crawler_id or 'auto-generated'}
   Region: {args.region}
   Redis: {args.redis_url}
   Log Level: {args.log_level}
""")
    
    async def run_crawler():
        async with SatelliteCrawler(
            redis_url=args.redis_url,
            crawler_id=args.crawler_id,
            region=args.region
        ) as crawler:
            await crawler.start()
    
    try:
        asyncio.run(run_crawler())
    except KeyboardInterrupt:
        print("\n🛑 Crawler stopped by user")
    except Exception as e:
        print(f"❌ Crawler failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
