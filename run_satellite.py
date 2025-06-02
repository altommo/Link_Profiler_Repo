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
from Link_Profiler.config.config_loader import config_loader # Import config_loader instance

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
    parser.add_argument("--database-url", default=None, # Added database-url argument
                       help="PostgreSQL database connection URL (overrides config/env)")
    
    args = parser.parse_args()
    
    # Configure logging
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Explicitly load config for standalone satellite
    # This ensures environment variables (like LP_DATABASE_URL) are picked up
    config_loader.load_config(config_dir=os.path.join(project_root, "Link_Profiler", "config"), env_var_prefix="LP_")
    
    print(f"""
🛰️ Starting Link Profiler Satellite Crawler
   ID: {args.crawler_id or 'auto-generated'}
   Region: {args.region}
   Redis: {args.redis_url}
   Database: {args.database_url or config_loader.get("database.url", "postgresql://linkprofiler:secure_password_123@localhost:5432/link_profiler_db")}
   Log Level: {args.log_level}
""")
    
    async def run_crawler():
        async with SatelliteCrawler(
            redis_url=args.redis_url,
            crawler_id=args.crawler_id,
            region=args.region,
            database_url=args.database_url # Pass the database_url argument
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
