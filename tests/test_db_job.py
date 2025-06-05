#!/usr/bin/env python3
"""
Test script to debug the database job submission issue
"""

from Link_Profiler.database.database import Database
from Link_Profiler.core.models import CrawlJob, CrawlStatus
from datetime import datetime
import uuid
import sys
import traceback

def main():
    print('Testing database connection...')
    db = Database('postgresql://postgres:postgres@localhost:5432/link_profiler_db')

    # Try to create a test job
    test_job = CrawlJob(
        id=str(uuid.uuid4()),
        target_url='https://example.com',
        job_type='test',
        status=CrawlStatus.PENDING,
        created_date=datetime.now(),
        config={},
        priority=5
    )

    print(f'Creating test job with ID: {test_job.id}')
    try:
        db.add_crawl_job(test_job)
        print('Job added successfully to database')
        
        # Try to retrieve it
        retrieved_job = db.get_crawl_job(test_job.id)
        if retrieved_job:
            print(f'Job retrieved successfully: {retrieved_job.id} - Status: {retrieved_job.status}')
        else:
            print('ERROR: Job not found in database after adding!')
            
        # Try to get all jobs
        all_jobs = db.get_all_crawl_jobs()
        print(f'Total jobs in database: {len(all_jobs)}')
        
        # Print first few jobs for debugging
        for i, job in enumerate(all_jobs[:5]):
            print(f'Job {i+1}: ID={job.id[:8]}..., Type={job.job_type}, Status={job.status}, Target={job.target_url}')
        
    except Exception as e:
        print(f'ERROR: {e}')
        traceback.print_exc()

if __name__ == "__main__":
    main()
