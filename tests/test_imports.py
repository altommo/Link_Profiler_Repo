#!/usr/bin/env python3
"""
Test script to check if main.py imports work without errors
"""
import sys
import os

# Add the project root to path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

try:
    print("Testing imports...")
    
    # Test config loading
    from Link_Profiler.config.config_loader import ConfigLoader
    print("✓ ConfigLoader imported successfully")
    
    # Test database
    from Link_Profiler.database.database import Database
    print("✓ Database imported successfully")
    
    # Test dependencies
    from Link_Profiler.api.dependencies import get_current_user
    print("✓ Dependencies imported successfully")
    
    # Test queue
    from Link_Profiler.api.queue import queue_router
    print("✓ Queue router imported successfully")
    
    # Test schemas
    from Link_Profiler.api.schemas import StartCrawlRequest
    print("✓ StartCrawlRequest imported successfully")
    
    print("\n✓ All critical imports successful!")
    print("The API should be able to start now.")
    
except ImportError as e:
    print(f"✗ Import error: {e}")
    sys.exit(1)
except Exception as e:
    print(f"✗ Other error: {e}")
    sys.exit(1)
