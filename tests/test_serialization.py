#!/usr/bin/env python3
"""
Test script to verify JSON serialization of CrawlJob with sets
"""

import sys
import os
sys.path.append('/opt/Link_Profiler_Repo')

from Link_Profiler.core.models import CrawlJob, CrawlStatus, CrawlConfig, serialize_model
from datetime import datetime
import uuid
import json

def test_serialization():
    print("Testing CrawlJob serialization...")
    
    # Create a CrawlConfig with sets (which cause the JSON error)
    config = CrawlConfig(
        allowed_domains={'example.com', 'test.com'},
        blocked_domains={'spam.com'},
        max_depth=2
    )
    
    # Serialize the config properly
    config_dict = serialize_model(config)
    print(f"Serialized config: {config_dict}")
    
    # Create a job
    job = CrawlJob(
        id=str(uuid.uuid4()),
        target_url="https://example.com",
        job_type="test",
        status=CrawlStatus.PENDING,
        created_date=datetime.now(),
        config=config_dict  # Use the serialized config
    )
    
    # Test if the job can be JSON serialized
    job_dict = serialize_model(job)
    print(f"Serialized job keys: {list(job_dict.keys())}")
    
    # Test JSON serialization
    try:
        json_str = json.dumps(job_dict)
        print("✅ JSON serialization successful!")
        return True
    except Exception as e:
        print(f"❌ JSON serialization failed: {e}")
        return False

if __name__ == "__main__":
    test_serialization()
