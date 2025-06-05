#!/usr/bin/env python3
"""
Test script for queue system functionality
"""
import asyncio
import json
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

async def test_queue_system():
    try:
        from queue_system.job_coordinator import JobCoordinator
        print("✅ JobCoordinator import successful")
        
        # Test Redis connection
        async with JobCoordinator() as coordinator:
            stats = await coordinator.get_queue_stats()
            print(f"✅ Redis connection successful: {stats}")
            
        print("✅ All tests passed!")
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_queue_system())
    sys.exit(0 if success else 1)