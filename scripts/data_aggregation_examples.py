import httpx
import asyncio
import os
from dotenv import load_dotenv
import json
from datetime import datetime, timedelta

# Load environment variables from .env file
load_dotenv()

# --- Configuration ---
API_BASE_URL = "http://localhost:8000"
ADMIN_USERNAME = os.getenv("LP_MONITOR_USERNAME", "monitor_user")
ADMIN_PASSWORD = os.getenv("LP_MONITOR_PASSWORD", "change_me") # Ensure this is set in your .env

# --- Helper Functions ---

async def get_auth_token(client: httpx.AsyncClient) -> str:
    """Authenticates as admin user and returns JWT token."""
    print(f"Attempting to get auth token for user: {ADMIN_USERNAME}")
    try:
        response = await client.post(
            f"{API_BASE_URL}/token",
            data={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD}
        )
        response.raise_for_status()
        token_data = response.json()
        print("Authentication successful.")
        return token_data["access_token"]
    except httpx.HTTPStatusError as e:
        print(f"Authentication failed: {e.response.status_code} - {e.response.text}")
        raise
    except Exception as e:
        print(f"An unexpected error occurred during authentication: {e}")
        raise

async def submit_job(client: httpx.AsyncClient, token: str, endpoint: str, payload: dict) -> dict:
    """Submits a job to the API."""
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    print(f"\nSubmitting job to {endpoint} with payload: {json.dumps(payload, indent=2)}")
    try:
        response = await client.post(
            f"{API_BASE_URL}{endpoint}",
            headers=headers,
            json=payload
        )
        response.raise_for_status()
        job_response = response.json()
        print(f"Job submitted successfully. Response: {json.dumps(job_response, indent=2)}")
        return job_response
    except httpx.HTTPStatusError as e:
        print(f"Job submission failed: {e.response.status_code} - {e.response.text}")
        raise
    except Exception as e:
        print(f"An unexpected error occurred during job submission: {e}")
        raise

async def get_job_status(client: httpx.AsyncClient, token: str, job_id: str) -> dict:
    """Retrieves the status of a job."""
    headers = {"Authorization": f"Bearer {token}"}
    print(f"\nChecking status for job ID: {job_id}")
    try:
        response = await client.get(
            f"{API_BASE_URL}/api/queue/job_status/{job_id}",
            headers=headers
        )
        response.raise_for_status()
        status_data = response.json()
        print(f"Job status for {job_id}: {json.dumps(status_data, indent=2)}")
        return status_data
    except httpx.HTTPStatusError as e:
        print(f"Failed to get job status: {e.response.status_code} - {e.response.text}")
        raise
    except Exception as e:
        print(f"An unexpected error occurred while checking job status: {e}")
        raise

# --- Job Submission Functions ---

async def run_backlink_discovery_job(client: httpx.AsyncClient, token: str, target_url: str, initial_seed_urls: list):
    """Submits a backlink discovery job."""
    payload = {
        "target_url": target_url,
        "initial_seed_urls": initial_seed_urls,
        "config": {
            "job_type": "backlink_discovery",
            "max_depth": 1, # Keep depth low for initial tests
            "max_pages": 10, # Limit pages for initial tests
            "render_javascript": True # Enable if target sites use JS
        }
    }
    return await submit_job(client, token, "/api/queue/submit_crawl", payload)

async def run_domain_analysis_job(client: httpx.AsyncClient, token: str, domain_names: list):
    """Submits a domain analysis job."""
    payload = {
        "domain_names": domain_names,
        "config": {
            "job_type": "domain_analysis"
        }
    }
    return await submit_job(client, token, "/api/queue/submit_crawl", payload)

async def run_serp_analysis_job(client: httpx.AsyncClient, token: str, keyword: str, num_results: int = 10):
    """Submits a SERP analysis job."""
    payload = {
        "target_url": f"https://www.google.com/search?q={keyword}", # Target URL is just for job tracking
        "keyword": keyword,
        "num_results": num_results,
        "config": {
            "job_type": "serp_analysis",
            "render_javascript": True # SERP crawling often benefits from JS rendering
        }
    }
    return await submit_job(client, token, "/api/queue/submit_crawl", payload)

async def run_keyword_research_job(client: httpx.AsyncClient, token: str, seed_keyword: str, num_suggestions: int = 5):
    """Submits a keyword research job."""
    payload = {
        "target_url": f"https://example.com/keywords/{seed_keyword}", # Dummy target URL
        "keyword": seed_keyword, # Used as seed_keyword in service
        "num_results": num_suggestions, # Used as num_suggestions in service
        "config": {
            "job_type": "keyword_research"
        }
    }
    return await submit_job(client, token, "/api/queue/submit_crawl", payload)

async def run_content_gap_analysis_job(client: httpx.AsyncClient, token: str, target_url: str, competitor_urls: list):
    """Submits a content gap analysis job."""
    payload = {
        "target_url": target_url,
        "content_gap_target_url": target_url, # Service expects this
        "content_gap_competitor_urls": competitor_urls, # Service expects this
        "config": {
            "job_type": "content_gap_analysis"
        }
    }
    return await submit_job(client, token, "/api/queue/submit_crawl", payload)

async def run_link_building_prospect_job(client: httpx.AsyncClient, token: str, target_domain: str, competitor_domains: list, keywords: list):
    """Submits a link building prospect identification job."""
    payload = {
        "target_url": f"https://{target_domain}", # Dummy target URL
        "link_prospect_target_domain": target_domain,
        "link_prospect_competitor_domains": competitor_domains,
        "link_prospect_keywords": keywords,
        "config": {
            "job_type": "prospect_identification"
        }
    }
    return await submit_job(client, token, "/api/queue/submit_crawl", payload)

# --- Main Execution ---

async def main():
    async with httpx.AsyncClient() as client:
        try:
            token = await get_auth_token(client)

            # --- Example 1: Backlink Discovery (using OpenLinkProfiler and simulated crawler) ---
            print("\n--- Running Backlink Discovery Job ---")
            backlink_job_response = await run_backlink_discovery_job(
                client, token,
                target_url="http://quotes.toscrape.com/", # A simple site for testing
                initial_seed_urls=["http://quotes.toscrape.com/"]
            )
            backlink_job_id = backlink_job_response["job_id"]
            await asyncio.sleep(5) # Give job some time to process
            await get_job_status(client, token, backlink_job_id)

            # --- Example 2: Domain Analysis (using direct DNS/WHOIS lookups) ---
            print("\n--- Running Domain Analysis Job ---")
            domain_job_response = await run_domain_analysis_job(
                client, token,
                domain_names=["example.com", "google.com", "nonexistentdomain12345.com"]
            )
            domain_job_id = domain_job_response["job_id"]
            await asyncio.sleep(5)
            await get_job_status(client, token, domain_job_id)

            # --- Example 3: SERP Analysis (using simulated SERP API/crawler) ---
            print("\n--- Running SERP Analysis Job ---")
            serp_job_response = await run_serp_analysis_job(
                client, token,
                keyword="best SEO tools",
                num_results=5
            )
            serp_job_id = serp_job_response["job_id"]
            await asyncio.sleep(5)
            await get_job_status(client, token, serp_job_id)

            # --- Example 4: Keyword Research (using simulated Keyword API) ---
            print("\n--- Running Keyword Research Job ---")
            keyword_job_response = await run_keyword_research_job(
                client, token,
                seed_keyword="link building strategies",
                num_suggestions=3
            )
            keyword_job_id = keyword_job_response["job_id"]
            await asyncio.sleep(5)
            await get_job_status(client, token, keyword_job_id)

            # --- Example 5: Content Gap Analysis (using simulated AI) ---
            print("\n--- Running Content Gap Analysis Job ---")
            content_gap_job_response = await run_content_gap_analysis_job(
                client, token,
                target_url="https://www.example.com/my-seo-guide",
                competitor_urls=["https://www.competitor1.com/seo-tips", "https://www.competitor2.com/seo-basics"]
            )
            content_gap_job_id = content_gap_job_response["job_id"]
            await asyncio.sleep(5)
            await get_job_status(client, token, content_gap_job_id)

            # --- Example 6: Link Building Prospect Identification (using simulated data) ---
            print("\n--- Running Link Building Prospect Identification Job ---")
            prospect_job_response = await run_link_building_prospect_job(
                client, token,
                target_domain="yourdomain.com",
                competitor_domains=["competitorA.com", "competitorB.com"],
                keywords=["seo software", "digital marketing agency"]
            )
            prospect_job_id = prospect_job_response["job_id"]
            await asyncio.sleep(5)
            await get_job_status(client, token, prospect_job_id)


            print("\n--- All example jobs submitted. Check your database for aggregated data. ---")

        except Exception as e:
            print(f"\nScript failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
