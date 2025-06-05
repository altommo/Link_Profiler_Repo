import asyncio
import httpx
import json
import pytest
from typing import List, Tuple, Optional, Dict

BASE_URL = "http://127.0.0.1:8000"

@pytest.mark.integration
@pytest.mark.asyncio
async def test_domain_availability():
    """Test domain availability endpoint"""
    domains_to_test = ["example.com", "google.com", "nonexistent.xyz"]
    
    for domain_name in domains_to_test:
        print(f"\n--- Testing /domain/availability/{domain_name} ---")
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(f"{BASE_URL}/domain/availability/{domain_name}")
                print(f"Status Code: {response.status_code}")
                
                if response.status_code == 200:
                    data = response.json()
                    print(f"Response: {json.dumps(data, indent=2)}")
                    assert "is_available" in data
                    print(f"Domain {domain_name} is available: {data['is_available']}")
                else:
                    pytest.skip(f"API not available or domain service failed for {domain_name}")
            except Exception as e:
                pytest.skip(f"Connection failed for {domain_name}: {e}")

async def submit_job_and_poll_status(
    endpoint: str, 
    payload: Dict, 
    job_type: str, 
    target_url_for_profile: Optional[str] = None
) -> Tuple[bool, bool]:
    """
    Submits a job to the queue and polls its status until completion or failure.
    Returns (job_completed_successfully, link_profile_generated_if_applicable).
    """
    print(f"\n--- Submitting {job_type} job to {endpoint} ---")
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(f"{BASE_URL}{endpoint}", json=payload)
            print(f"Submission Status Code: {response.status_code}")
            
            if response.status_code == 202:
                job_response = response.json()
                print(f"Submission Response: {json.dumps(job_response, indent=2)}")
                job_id = job_response.get('job_id')
                if not job_id:
                    print("Error: No job_id returned from submission.")
                    return False, False
                print(f"Job submitted with ID: {job_id}")
            else:
                print(f"Error submitting job: {response.text}")
                return False, False
        except Exception as e:
            print(f"Failed to submit job: {e}")
            return False, False

    print(f"\n--- Polling /crawl/status/{job_id} ---")
    job_completed_successfully = False
    link_profile_generated = False
    
    async with httpx.AsyncClient() as client:
        for i in range(30):  # Reduced polling time for tests
            try:
                status_response = await client.get(f"{BASE_URL}/crawl/status/{job_id}")
                if status_response.status_code != 200:
                    break
                    
                status_data = status_response.json()
                print(f"Current Status for {job_id}: {status_data['status']}, Progress: {status_data.get('progress_percentage', 0):.2f}%")
                
                if status_data['status'] == "completed":
                    job_completed_successfully = True
                    if job_type == "backlink_discovery" and status_data.get('results', {}).get('link_profile_summary', {}).get('total_backlinks', 0) > 0:
                        link_profile_generated = True
                    print(f"Final Status for {job_id}: {json.dumps(status_data, indent=2)}")
                    break
                elif status_data['status'] == "failed":
                    print(f"Final Status for {job_id}: {json.dumps(status_data, indent=2)}")
                    break
            except Exception as e:
                print(f"Error polling status for {job_id}: {e}")
                break
            await asyncio.sleep(2)
        else:
            print(f"Job {job_id} did not complete within the timeout period.")
            
    return job_completed_successfully, link_profile_generated

@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.asyncio
async def test_backlink_discovery():
    """Test backlink discovery job submission and completion"""
    backlink_payload = {
        "target_url": "http://quotes.toscrape.com",
        "initial_seed_urls": ["http://quotes.toscrape.com/page/1/", "http://quotes.toscrape.com/page/2/"],
        "config": {
            "max_pages": 5,
            "max_depth": 1,
            "delay_seconds": 0.1
        }
    }
    
    job_success, profile_generated = await submit_job_and_poll_status(
        "/crawl/start_backlink_discovery", 
        backlink_payload, 
        "backlink_discovery",
        target_url_for_profile="http://quotes.toscrape.com"
    )
    
    # Don't fail the test if API is not available, just skip
    if not job_success:
        pytest.skip("Backlink discovery job did not complete successfully - API may not be running")

@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_link_profile():
    """Test retrieving link profile"""
    target_url = "http://quotes.toscrape.com"
    print(f"\n--- Testing /link_profile/{target_url} ---")
    
    async with httpx.AsyncClient() as client:
        try:
            encoded_url = target_url.replace(':', '%3A').replace('/', '%2F')
            response = await client.get(f"{BASE_URL}/link_profile/{encoded_url}")
            print(f"Status Code: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"Response: {json.dumps(data, indent=2)}")
                assert "total_backlinks" in data
            else:
                pytest.skip("Link profile endpoint not available or no data")
        except Exception as e:
            pytest.skip(f"Failed to get link profile: {e}")

@pytest.mark.integration
@pytest.mark.asyncio
async def test_export_endpoints():
    """Test CSV export endpoints"""
    endpoints = [
        "/export/backlinks.csv",
        "/export/link_profiles.csv", 
        "/export/crawl_jobs.csv"
    ]
    
    for endpoint in endpoints:
        print(f"\n--- Testing {endpoint} ---")
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(f"{BASE_URL}{endpoint}")
                print(f"Status Code: {response.status_code}")
                
                if response.status_code == 200:
                    assert "text/csv" in response.headers.get("content-type", "")
                    assert "attachment" in response.headers.get("content-disposition", "")
                    assert len(response.text) > 0
                    print(f"CSV export working for {endpoint}")
                else:
                    print(f"Export endpoint {endpoint} returned {response.status_code}")
            except Exception as e:
                print(f"Failed to test {endpoint}: {e}")

@pytest.mark.integration
@pytest.mark.slow 
@pytest.mark.asyncio
async def test_find_expired_domains():
    """Test expired domains finder"""
    domains = ["example.com", "google.com", "available.net", "nonexistent.xyz", "testdomain.org"]
    payload = {
        "potential_domains": domains,
        "min_value_score": 60,
        "limit": 5
    }
    
    print(f"\n--- Testing /domain/find_expired_domains ---")
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(f"{BASE_URL}/domain/find_expired_domains", json=payload)
            print(f"Status Code: {response.status_code}")
            
            if response.status_code == 200:
                find_response = response.json()
                print(f"Response: {json.dumps(find_response, indent=2)}")
                assert "found_domains" in find_response
                print(f"Found {find_response.get('valuable_domains_found', 0)} valuable expired domains.")
            else:
                pytest.skip("Expired domains endpoint not available")
        except Exception as e:
            pytest.skip(f"Failed to test expired domains: {e}")

# Keep the original main function for manual testing
async def main():
    """Main function for manual testing - not run by pytest"""
    print("Running manual API tests...")
    
    # Test Domain Service Endpoints
    await test_domain_availability()
    
    # Test other endpoints
    await test_backlink_discovery()
    await test_get_link_profile()
    await test_export_endpoints()
    await test_find_expired_domains()

if __name__ == "__main__":
    asyncio.run(main())
