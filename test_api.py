import asyncio
import httpx
import json
from typing import List # Import List

BASE_URL = "http://127.0.0.1:8000"

async def test_domain_availability(domain_name: str):
    print(f"\n--- Testing /domain/availability/{domain_name} ---")
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/domain/availability/{domain_name}")
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        response.raise_for_status() # Raise an exception for bad status codes
        assert "is_available" in response.json()
        print(f"Domain {domain_name} is available: {response.json()['is_available']}")

async def test_start_crawl_job(target_url: str, initial_seed_urls: List[str]):
    print(f"\n--- Testing /crawl/start_backlink_discovery for {target_url} ---")
    payload = {
        "target_url": target_url,
        "initial_seed_urls": initial_seed_urls,
        "config": {
            "max_pages": 5,
            "max_depth": 1,
            "delay_seconds": 0.1
        }
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(f"{BASE_URL}/crawl/start_backlink_discovery", json=payload)
        print(f"Status Code: {response.status_code}")
        job_response = response.json()
        print(f"Response: {json.dumps(job_response, indent=2)}")
        response.raise_for_status()
        assert "id" in job_response
        print(f"Crawl job started with ID: {job_response['id']}")
        return job_response['id']

async def test_get_crawl_status(job_id: str):
    print(f"\n--- Testing /crawl/status/{job_id} ---")
    async with httpx.AsyncClient() as client:
        # Poll status until completed or failed
        while True:
            response = await client.get(f"{BASE_URL}/crawl/status/{job_id}")
            print(f"Status Code: {response.status_code}")
            status_response = response.json()
            print(f"Current Status: {status_response['status']}, Progress: {status_response['progress_percentage']:.2f}%")
            if status_response['status'] in ["completed", "failed"]:
                print(f"Final Status: {json.dumps(status_response, indent=2)}")
                break
            await asyncio.sleep(2) # Wait a bit before polling again

async def test_get_link_profile(target_url: str):
    print(f"\n--- Testing /link_profile/{target_url} ---")
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/link_profile/{target_url.replace(':', '%3A').replace('/', '%2F')}") # URL-encode path
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        response.raise_for_status()
        assert "total_backlinks" in response.json()

async def test_find_expired_domains(domains: List[str]):
    print(f"\n--- Testing /domain/find_expired_domains ---")
    payload = {
        "potential_domains": domains,
        "min_value_score": 60,
        "limit": 5
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(f"{BASE_URL}/domain/find_expired_domains", json=payload)
        print(f"Status Code: {response.status_code}")
        find_response = response.json()
        print(f"Response: {json.dumps(find_response, indent=2)}")
        response.raise_for_status()
        assert "found_domains" in find_response
        print(f"Found {find_response['valuable_domains_found']} valuable expired domains.")


async def main():
    # Test Domain Service Endpoints
    await test_domain_availability("example.com")
    await test_domain_availability("google.com")
    await test_domain_availability("nonexistent.xyz")

    # Test Crawl Service Endpoints
    # Note: These URLs don't need to be real, but the crawler will attempt to connect.
    # For a more realistic test, use actual websites that you have permission to crawl.
    crawl_job_id = await test_start_crawl_job(
        "http://testtarget.com",
        ["http://testsource1.com/page", "http://testsource2.com/another-page"]
    )
    if crawl_job_id:
        await test_get_crawl_status(crawl_job_id)
        await test_get_link_profile("http://testtarget.com")

    # Test Expired Domain Finder
    await test_find_expired_domains(["example.com", "google.com", "available.net", "nonexistent.xyz", "testdomain.org"])

if __name__ == "__main__":
    asyncio.run(main())
