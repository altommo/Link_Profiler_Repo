#!/usr/bin/env python3
"""
Test script to verify imports work correctly after constructor fixes
"""
import sys
import os

# Add project root to path
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    # Test basic config loading
    from Link_Profiler.config.config_loader import config_loader
    print("[OK] Config loader imported successfully")
    
    # Test service imports
    from Link_Profiler.services.backlink_service import BacklinkService
    print("[OK] BacklinkService imported successfully")
    
    from Link_Profiler.services.serp_service import SERPService
    print("[OK] SERPService imported successfully")
    
    from Link_Profiler.services.keyword_service import KeywordService
    print("[OK] KeywordService imported successfully")
    
    from Link_Profiler.services.ai_service import AIService
    print("[OK] AIService imported successfully")
    
    from Link_Profiler.services.social_media_service import SocialMediaService
    print("[OK] SocialMediaService imported successfully")
    
    from Link_Profiler.services.web3_service import Web3Service
    print("[OK] Web3Service imported successfully")
    
    # Test crawler imports
    from Link_Profiler.crawlers.serp_crawler import SERPCrawler
    print("[OK] SERPCrawler imported successfully")
    
    from Link_Profiler.crawlers.keyword_scraper import KeywordScraper
    print("[OK] KeywordScraper imported successfully")
    
    from Link_Profiler.crawlers.social_media_crawler import SocialMediaCrawler
    print("[OK] SocialMediaCrawler imported successfully")
    
    print("\n[SUCCESS] All imports successful! Constructor fixes should be working.")
    
except ImportError as e:
    print(f"[ERROR] Import error: {e}")
    sys.exit(1)
except Exception as e:
    print(f"[ERROR] Unexpected error: {e}")
    sys.exit(1)
