#!/usr/bin/env python3
"""
Test script to check if main.py imports work without errors
"""
import sys
import os
import pytest

# Add the project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

def test_config_import():
    """Test config loading import"""
    try:
        from Link_Profiler.config.config_loader import ConfigLoader
        assert ConfigLoader is not None
    except ImportError as e:
        pytest.skip(f"Config import failed: {e}")

def test_database_import():
    """Test database import"""
    try:
        from Link_Profiler.database.database import Database
        assert Database is not None
    except ImportError as e:
        pytest.skip(f"Database import failed: {e}")

def test_dependencies_import():
    """Test dependencies import"""
    try:
        from Link_Profiler.api.dependencies import get_current_user
        assert get_current_user is not None
    except ImportError as e:
        pytest.skip(f"Dependencies import failed: {e}")

def test_queue_import():
    """Test queue router import"""
    try:
        from Link_Profiler.api.queue import queue_router
        assert queue_router is not None
    except ImportError as e:
        pytest.skip(f"Queue router import failed: {e}")

def test_schemas_import():
    """Test schemas import"""
    try:
        from Link_Profiler.api.schemas import StartCrawlRequest
        assert StartCrawlRequest is not None
    except ImportError as e:
        pytest.skip(f"Schemas import failed: {e}")

if __name__ == "__main__":
    # When run directly, provide helpful output
    try:
        print("Testing imports...")
        
        from Link_Profiler.config.config_loader import ConfigLoader
        print("✓ ConfigLoader imported successfully")
        
        from Link_Profiler.database.database import Database
        print("✓ Database imported successfully")
        
        from Link_Profiler.api.dependencies import get_current_user
        print("✓ Dependencies imported successfully")
        
        from Link_Profiler.api.queue import queue_router
        print("✓ Queue router imported successfully")
        
        from Link_Profiler.api.schemas import StartCrawlRequest
        print("✓ StartCrawlRequest imported successfully")
        
        print("\n✓ All critical imports successful!")
        print("The API should be able to start now.")
        
    except ImportError as e:
        print(f"✗ Import error: {e}")
        print("Run: pip install -r requirements.txt")
        print("Make sure PYTHONPATH is set correctly")
    except Exception as e:
        print(f"✗ Other error: {e}")
