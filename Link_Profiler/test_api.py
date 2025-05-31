import asyncio
import httpx
import json
from typing import List, Tuple, Optional, Dict # Import Tuple, Optional, Dict

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
            response.raise_for_status()
            return False, False

    print(f"\n--- Polling /crawl/status/{job_id} ---")
    job_completed_successfully = False
    link_profile_generated = False # Only relevant for backlink_discovery
    
    async with httpx.AsyncClient() as client:
        for _ in range(60): # Poll for up to 120 seconds (60 * 2s)
            try:
                status_response = await client.get(f"{BASE_URL}/crawl/status/{job_id}")
                status_response.raise_for_status()
                status_data = status_response.json()
                
                print(f"Current Status for {job_id}: {status_data['status']}, Progress: {status_data['progress_percentage']:.2f}%")
                
                if status_data['status'] == "completed":
                    job_completed_successfully = True
                    if job_type == "backlink_discovery" and status_data.get('results', {}).get('link_profile_summary', {}).get('total_backlinks', 0) > 0:
                        link_profile_generated = True
                    print(f"Final Status for {job_id}: {json.dumps(status_data, indent=2)}")
                    break
                elif status_data['status'] == "failed":
                    print(f"Final Status for {job_id}: {json.dumps(status_data, indent=2)}")
                    break
            except httpx.HTTPStatusError as e:
                print(f"HTTP Error polling status for {job_id}: {e.response.status_code} - {e.response.text}")
                break
            except Exception as e:
                print(f"Unexpected Error polling status for {job_id}: {e}")
                break
            await asyncio.sleep(2)
        else:
            print(f"Job {job_id} did not complete within the timeout period.")
            
    return job_completed_successfully, link_profile_generated


async def test_get_link_profile(target_url: str):
    print(f"\n--- Testing /link_profile/{target_url} ---")
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/link_profile/{target_url.replace(':', '%3A').replace('/', '%2F')}") # URL-encode path
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        response.raise_for_status()
        assert "total_backlinks" in response.json()

async def test_get_backlinks(target_url: str):
    print(f"\n--- Testing /backlinks/{target_url} ---")
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/backlinks/{target_url.replace(':', '%3A').replace('/', '%2F')}") # URL-encode path
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        response.raise_for_status()
        assert isinstance(response.json(), list)

async def test_find_expired_domains(domains: List[str]):
    print(f"\n--- Testing /domain/find_expired_domains ---")
    payload = {
        "potential_domains": domains,
        "min_value_score": 60,
        "limit": 5
    }
    # Increase timeout for this specific test as it involves multiple simulated API calls
    async with httpx.AsyncClient(timeout=30.0) as client: # Increased timeout to 30 seconds
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

    # Test Backlink Discovery (submitted to queue)
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
    if job_success and profile_generated:
        try:
            await test_get_link_profile("http://quotes.toscrape.com")
            await test_get_backlinks("http://quotes.toscrape.com")
        except httpx.HTTPStatusError as e:
            print(f"Warning: Could not retrieve link profile or backlinks: {e.response.status_code} - {e.response.json().get('detail', 'Unknown error')}")
    else:
        print("Skipping link profile and backlinks tests as crawl job did not complete successfully or no profile was generated.")

    # Test Expired Domain Finder
    await test_find_expired_domains(["example.com", "google.com", "available.net", "nonexistent.xyz", "testdomain.org"])

    # Test SERP Search (submitted to queue)
    serp_payload = {
        "keyword": "python programming",
        "num_results": 3,
        "search_engine": "google"
    }
    serp_payload["config"] = {"keyword": serp_payload["keyword"], "num_results": serp_payload["num_results"], "search_engine": serp_payload["search_engine"], "job_type": "serp_analysis"}
    serp_payload["target_url"] = serp_payload["keyword"] # Set target_url for QueueCrawlRequest
    serp_payload["initial_seed_urls"] = [] # Required by QueueCrawlRequest
    
    job_success, _ = await submit_job_and_poll_status(
        "/serp/search", 
        serp_payload, 
        "serp_analysis"
    )
    if job_success:
        print(f"SERP search job completed. Retrieving results for '{serp_payload['keyword']}'...")
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{BASE_URL}/serp/results/{serp_payload['keyword']}")
            print(f"Status Code: {response.status_code}")
            print(f"Response: {json.dumps(response.json(), indent=2)}")
            response.raise_for_status()
            assert isinstance(response.json(), list) and len(response.json()) > 0
    else:
        print(f"SERP search job for '{serp_payload['keyword']}' did not complete successfully.")

    # Test Keyword Suggestion (submitted to queue)
    keyword_payload = {
        "seed_keyword": "data science",
        "num_suggestions": 5
    }
    keyword_payload["config"] = {"seed_keyword": keyword_payload["seed_keyword"], "num_suggestions": keyword_payload["num_suggestions"], "job_type": "keyword_research"}
    keyword_payload["target_url"] = keyword_payload["seed_keyword"] # Set target_url for QueueCrawlRequest
    keyword_payload["initial_seed_urls"] = [] # Required by QueueCrawlRequest

    job_success, _ = await submit_job_and_poll_status(
        "/keyword/suggest", 
        keyword_payload, 
        "keyword_research"
    )
    if job_success:
        print(f"Keyword suggestion job completed. Retrieving results for '{keyword_payload['seed_keyword']}'...")
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{BASE_URL}/keyword/suggestions/{keyword_payload['seed_keyword']}")
            print(f"Status Code: {response.status_code}")
            print(f"Response: {json.dumps(response.json(), indent=2)}")
            response.raise_for_status()
            assert isinstance(response.json(), list) and len(response.json()) > 0
    else:
        print(f"Keyword suggestion job for '{keyword_payload['seed_keyword']}' did not complete successfully.")

    # Test Link Health Audit (submitted to queue)
    link_health_urls = ["http://quotes.toscrape.com/page/1/", "http://example.com/broken-links-test"]
    link_health_payload = {
        "source_urls": link_health_urls
    }
    link_health_payload["config"] = {"source_urls_to_audit": link_health_urls, "job_type": "link_health_audit"}
    link_health_payload["target_url"] = link_health_urls[0] # Set target_url for QueueCrawlRequest
    link_health_payload["initial_seed_urls"] = link_health_urls # Required by QueueCrawlRequest
    
    job_success, _ = await submit_job_and_poll_status(
        "/audit/link_health", 
        link_health_payload, 
        "link_health_audit"
    )
    if job_success:
        print(f"Link health audit job completed.")
        # Further checks would involve retrieving job results from /crawl/status/{job_id}
        # and inspecting the 'broken_links_audit' field.
    else:
        print(f"Link health audit job did not complete successfully.")

    # Test Technical Audit (submitted to queue)
    tech_audit_urls = ["http://quotes.toscrape.com/", "https://www.google.com/"]
    tech_audit_payload = {
        "urls_to_audit": tech_audit_urls,
        "config": {"user_agent": "TestAuditor/1.0"}
    }
    tech_audit_payload["config"]["urls_to_audit_tech"] = tech_audit_urls # Pass actual list
    tech_audit_payload["config"]["job_type"] = "technical_audit"
    tech_audit_payload["target_url"] = tech_audit_urls[0] # Set target_url for QueueCrawlRequest
    tech_audit_payload["initial_seed_urls"] = tech_audit_urls # Required by QueueCrawlRequest

    job_success, _ = await submit_job_and_poll_status(
        "/audit/technical_audit", 
        tech_audit_payload, 
        "technical_audit"
    )
    if job_success:
        print(f"Technical audit job completed.")
        # Further checks would involve retrieving job results from /crawl/status/{job_id}
        # and inspecting the 'seo_metrics' for the audited URLs.
    else:
        print(f"Technical audit job did not complete successfully.")


if __name__ == "__main__":
    asyncio.run(main())
