# Link Profiler API Commands Reference

This document provides `curl` commands for interacting with the Link Profiler API.
Replace `YOUR_API_HOST` with your actual API domain (e.g., `api.yspanel.com`).
Replace `YOUR_MONITOR_HOST` with your actual monitoring dashboard domain (e.g., `monitor.yspanel.com`).
Replace `YOUR_TOKEN` with a valid JWT access token obtained from the `/auth/token` endpoint.
Replace `YOUR_JOB_ID` with an actual job identifier.
Replace `YOUR_USERNAME` and `YOUR_PASSWORD` with valid user credentials.

---

## 🔐 Authentication Endpoints

### 1. Register a New User
Registers a new user in the system.
```bash
curl -X POST "https://YOUR_API_HOST/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "newuser",
    "email": "newuser@example.com",
    "password": "secure_password_for_new_user"
  }'
```

### 2. Obtain an Access Token (Login)
Authenticates a user and returns a JWT access token. This token should be used in the `Authorization: Bearer YOUR_TOKEN` header for protected endpoints.
```bash
curl -X POST "https://YOUR_API_HOST/auth/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=your_username&password=your_password"
```
*Example Response (copy `access_token` value):*
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

### 3. Get Current Authenticated User Information
Retrieves details of the currently authenticated user.
```bash
TOKEN="YOUR_TOKEN" # Replace with your actual token
curl -X GET "https://YOUR_API_HOST/users/me" \
  -H "Authorization: Bearer $TOKEN"
```

---

## 🚀 Job Submission Endpoints (Unified `/api/jobs`)

All job types can be submitted via the `POST /api/jobs` endpoint by specifying the `job_type` within the `config` payload.

### General Job Submission Structure
```bash
TOKEN="YOUR_TOKEN" # Replace with your actual token
curl -X POST "https://YOUR_API_HOST/api/jobs" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "target_url": "https://example.com",
    "initial_seed_urls": ["https://example.com/start"],
    "priority": 5,
    "config": {
      "job_type": "YOUR_JOB_TYPE",
      "max_depth": 2,
      "max_pages": 100,
      "delay_seconds": 1.0,
      "render_javascript": false,
      "extract_images": true,
      "extract_pdfs": false,
      "allowed_domains": [],
      "blocked_domains": [],
      "use_proxies": false,
      "proxy_region": null,
      "anomaly_detection_enabled": false,
      "captcha_solving_enabled": false,
      "extract_image_text": false,
      "crawl_web3_content": false,
      "crawl_social_media": false,
      "extract_video_content": false,
      "custom_job_param_1": "value1",
      "custom_job_param_2": "value2"
    },
    "scheduled_at": null,
    "cron_schedule": null
  }'
```

### 1. Submit Backlink Discovery Job
Crawls specified seed URLs to find backlinks to the target URL.
```bash
TOKEN="YOUR_TOKEN"
curl -X POST "https://YOUR_API_HOST/api/jobs" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "target_url": "https://yourtargetdomain.com",
    "initial_seed_urls": ["https://competitor1.com/blog", "https://nicheforum.com/threads/link-building"],
    "priority": 5,
    "config": {
      "job_type": "backlink_discovery",
      "max_depth": 2,
      "max_pages": 500,
      "delay_seconds": 1.5,
      "respect_robots_txt": true,
      "render_javascript": false
    }
  }'
```

### 2. Submit Link Health Audit Job
Audits outgoing links from a list of source URLs for brokenness.
```bash
TOKEN="YOUR_TOKEN"
curl -X POST "https://YOUR_API_HOST/api/jobs" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "target_url": "https://yourdomain.com/audit-report",
    "initial_seed_urls": ["https://yourdomain.com/page1", "https://yourdomain.com/page2"],
    "priority": 7,
    "config": {
      "job_type": "link_health_audit",
      "source_urls_to_audit": ["https://yourdomain.com/page1", "https://yourdomain.com/page2"],
      "timeout_seconds": 45
    }
  }'
```

### 3. Submit Technical Audit Job
Performs a technical SEO audit (e.g., using Lighthouse) on specified URLs.
```bash
TOKEN="YOUR_TOKEN"
curl -X POST "https://YOUR_API_HOST/api/jobs" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "target_url": "https://yourdomain.com/technical-audit-summary",
    "initial_seed_urls": ["https://yourdomain.com/homepage", "https://yourdomain.com/product-page"],
    "priority": 8,
    "config": {
      "job_type": "technical_audit",
      "urls_to_audit_tech": ["https://yourdomain.com/homepage", "https://yourdomain.com/product-page"],
      "render_javascript": true,
      "headless_browser": true
    }
  }'
```

### 4. Submit Full SEO Audit Job
Orchestrates both technical and link health audits for specified URLs.
```bash
TOKEN="YOUR_TOKEN"
curl -X POST "https://YOUR_API_HOST/api/jobs" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "target_url": "https://yourdomain.com/full-seo-report",
    "initial_seed_urls": ["https://yourdomain.com/about", "https://yourdomain.com/contact"],
    "priority": 9,
    "config": {
      "job_type": "full_seo_audit",
      "urls_to_audit_full_seo": ["https://yourdomain.com/about", "https://yourdomain.com/contact"],
      "render_javascript": true
    }
  }'
```

### 5. Submit Domain Analysis Job
Analyzes a batch of domain names for various metrics and value.
```bash
TOKEN="YOUR_TOKEN"
curl -X POST "https://YOUR_API_HOST/api/jobs" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "target_url": "domain_batch_analysis_report",
    "initial_seed_urls": [],
    "priority": 6,
    "config": {
      "job_type": "domain_analysis",
      "domain_names_to_analyze": ["expired-domain-1.com", "expired-domain-2.net"],
      "min_value_score": 60.0,
      "limit": 10
    }
  }'
```

### 6. Submit Web3 Crawl Job
Crawls content from Web3 identifiers (e.g., IPFS hashes).
```bash
TOKEN="YOUR_TOKEN"
curl -X POST "https://YOUR_API_HOST/api/jobs" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "target_url": "ipfs://QmYwAPJzv5CZsnA625s3Xf2nemtCEgfJqcdL",
    "initial_seed_urls": [],
    "priority": 4,
    "config": {
      "job_type": "web3_crawl",
      "web3_content_identifier": "ipfs://QmYwAPJzv5CZsnA625s3Xf2nemtCEgfJqcdL",
      "crawl_web3_content": true
    }
  }'
```

### 7. Submit Social Media Crawl Job
Crawls social media mentions for a specific query or brand.
```bash
TOKEN="YOUR_TOKEN"
curl -X POST "https://YOUR_API_HOST/api/jobs" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "target_url": "social_media_mentions_for_yourbrand",
    "initial_seed_urls": [],
    "priority": 6,
    "config": {
      "job_type": "social_media_crawl",
      "social_media_query": "#yourbrand",
      "platforms": ["twitter", "reddit"],
      "crawl_social_media": true
    }
  }'
```

### 8. Submit Content Gap Analysis Job
Analyzes content gaps between a target URL and competitor URLs using AI.
```bash
TOKEN="YOUR_TOKEN"
curl -X POST "https://YOUR_API_HOST/api/jobs" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "target_url": "https://yourdomain.com/content-strategy",
    "initial_seed_urls": [],
    "priority": 7,
    "config": {
      "job_type": "content_gap_analysis",
      "target_url_for_content_gap": "https://yourdomain.com/blog/topic-a",
      "competitor_urls_for_content_gap": ["https://competitor1.com/blog/topic-a", "https://competitor2.com/guides/topic-a"]
    }
  }'
```

### 9. Submit Prospect Identification Job
Identifies potential link building prospects based on competitor backlinks and keywords.
```bash
TOKEN="YOUR_TOKEN"
curl -X POST "https://YOUR_API_HOST/api/jobs" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "target_url": "https://yourdomain.com/link-prospects",
    "initial_seed_urls": [],
    "priority": 8,
    "config": {
      "job_type": "prospect_identification",
      "target_domain": "yourdomain.com",
      "competitor_domains": ["competitor1.com", "competitor2.com"],
      "keywords": ["best widgets", "widget reviews"],
      "min_domain_authority": 30.0,
      "max_spam_score": 0.2
    }
  }'
```

### 10. Submit Report Generation Job
Schedules the generation of a specific report.
```bash
TOKEN="YOUR_TOKEN"
curl -X POST "https://YOUR_API_HOST/api/jobs" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "target_url": "report_job_summary",
    "initial_seed_urls": [],
    "priority": 9,
    "config": {
      "job_type": "report_generation",
      "report_job_type": "link_profile_pdf",
      "report_target_identifier": "https://yourdomain.com",
      "report_format": "pdf",
      "report_config": {
        "include_backlinks": true,
        "include_seo_metrics": true
      }
    },
    "scheduled_at": "2025-06-03T10:00:00Z"
  }'
```

### 11. Schedule a Recurring Job
Schedules a job to run repeatedly using a cron expression.
```bash
TOKEN="YOUR_TOKEN"
curl -X POST "https://YOUR_API_HOST/api/jobs" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "target_url": "https://yourdomain.com/weekly-audit",
    "initial_seed_urls": ["https://yourdomain.com"],
    "priority": 5,
    "config": {
      "job_type": "link_health_audit",
      "source_urls_to_audit": ["https://yourdomain.com"]
    },
    "scheduled_at": "2025-06-03T00:00:00Z",
    "cron_schedule": "0 0 * * 1" # Every Monday at midnight UTC
  }'
```

---

## 📈 Job & Queue Management Endpoints

### 1. Get Job Status
Retrieves the current status of a specific job.
```bash
TOKEN="YOUR_TOKEN"
JOB_ID="YOUR_JOB_ID" # Replace with an actual job ID
curl -X GET "https://YOUR_API_HOST/queue/job_status/$JOB_ID" \
  -H "Authorization: Bearer $TOKEN"
```

### 2. Get Queue Statistics
Retrieves overall statistics about the job queues and active crawlers.
```bash
TOKEN="YOUR_TOKEN"
curl -X GET "https://YOUR_API_HOST/queue/stats" \
  -H "Authorization: Bearer $TOKEN"
```

### 3. Get Crawler Health
Retrieves detailed health information for all connected satellite crawlers.
```bash
TOKEN="YOUR_TOKEN"
curl -X GET "https://YOUR_API_HOST/queue/manage/crawler_health" \
  -H "Authorization: Bearer $TOKEN"
```

### 4. Submit a Sample Job (for testing)
Submits a predefined sample job to the queue.
```bash
TOKEN="YOUR_TOKEN"
curl -X POST "https://YOUR_API_HOST/queue/test/submit_sample_job" \
  -H "Authorization: Bearer $TOKEN"
```

---

## 📊 Data Retrieval Endpoints

### 1. Get Content Gap Analysis Result
Retrieves the result of a completed content gap analysis job for a target URL.
```bash
TOKEN="YOUR_TOKEN"
TARGET_URL_ENCODED="https%3A%2F%2Fyourdomain.com%2Fcontent-strategy" # URL-encode your target URL
curl -X GET "https://YOUR_API_HOST/content/gap_analysis/$TARGET_URL_ENCODED" \
  -H "Authorization: Bearer $TOKEN"
```

### 2. Perform Topic Clustering
Sends a list of texts to the AI service for topic clustering.
```bash
TOKEN="YOUR_TOKEN"
curl -X POST "https://YOUR_API_HOST/content/topic_clustering" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "texts": ["This is a text about SEO and backlinks.", "Another document discussing content marketing strategies.", "A third text on technical SEO audits."],
    "num_clusters": 2
  }'
```

### 3. Get Link Velocity for a Domain
Retrieves historical link acquisition rates for a domain.
```bash
TOKEN="YOUR_TOKEN"
DOMAIN_NAME="yourdomain.com"
curl -X GET "https://YOUR_API_HOST/link_profile/$DOMAIN_NAME/link_velocity?time_unit=month&num_units=6" \
  -H "Authorization: Bearer $TOKEN"
```

### 4. Get Domain History
Retrieves historical metrics for a specific domain.
```bash
TOKEN="YOUR_TOKEN"
DOMAIN_NAME="yourdomain.com"
curl -X GET "https://YOUR_API_HOST/domain/$DOMAIN_NAME/history?num_snapshots=12" \
  -H "Authorization: Bearer $TOKEN"
```

### 5. Get SERP Position History
Retrieves historical SERP positions for a specific URL and keyword.
```bash
TOKEN="YOUR_TOKEN"
TARGET_URL_ENCODED="https%3A%2F%2Fyourdomain.com%2Fproduct"
KEYWORD_ENCODED="best%20product"
curl -X GET "https://YOUR_API_HOST/serp/history?target_url=$TARGET_URL_ENCODED&keyword=$KEYWORD_ENCODED&num_snapshots=10" \
  -H "Authorization: Bearer $TOKEN"
```

### 6. Get Semantic Keyword Suggestions
Generates semantically related keywords using AI.
```bash
TOKEN="YOUR_TOKEN"
KEYWORD_ENCODED="content%20marketing"
curl -X POST "https://YOUR_API_HOST/keyword/semantic_suggestions?primary_keyword=$KEYWORD_ENCODED" \
  -H "Authorization: Bearer $TOKEN"
```

### 7. Perform Link Intersect Analysis
Finds common linking domains between a primary domain and its competitors.
```bash
TOKEN="YOUR_TOKEN"
curl -X POST "https://YOUR_API_HOST/competitor/link_intersect" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "primary_domain": "yourdomain.com",
    "competitor_domains": ["competitor1.com", "competitor2.com"]
  }'
```

### 8. Perform Competitive Keyword Analysis
Identifies common keywords, keyword gaps, and unique keywords for domains.
```bash
TOKEN="YOUR_TOKEN"
curl -X POST "https://YOUR_API_HOST/competitor/keyword_analysis" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "primary_domain": "yourdomain.com",
    "competitor_domains": ["competitor1.com", "competitor2.com"]
  }'
```

### 9. Get All Link Prospects
Retrieves all identified link building prospects, optionally filtered by status.
```bash
TOKEN="YOUR_TOKEN"
curl -X GET "https://YOUR_API_HOST/link_building/prospects?status_filter=identified" \
  -H "Authorization: Bearer $TOKEN"
```

### 10. Update Link Prospect Status
Updates the status or details of a specific link prospect.
```bash
TOKEN="YOUR_TOKEN"
PROSPECT_URL_ENCODED="https%3A%2F%2Fprospectsite.com%2Fcontact"
curl -X PUT "https://YOUR_API_HOST/link_building/prospects/$PROSPECT_URL_ENCODED" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "status": "contacted",
    "last_outreach_date": "2025-06-01T14:30:00Z",
    "contact_info": {"email": "info@prospectsite.com"}
  }'
```

### 11. Create Outreach Campaign
Creates a new link building outreach campaign.
```bash
TOKEN="YOUR_TOKEN"
curl -X POST "https://YOUR_API_HOST/link_building/campaigns" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "name": "Summer Link Building 2025",
    "target_domain": "yourdomain.com",
    "description": "Campaign to acquire links for new product launch."
  }'
```

### 12. Get All Outreach Campaigns
Retrieves all outreach campaigns, optionally filtered by status.
```bash
TOKEN="YOUR_TOKEN"
curl -X GET "https://YOUR_API_HOST/link_building/campaigns?status_filter=active" \
  -H "Authorization: Bearer $TOKEN"
```

### 13. Get Outreach Campaign by ID
Retrieves details of a specific outreach campaign.
```bash
TOKEN="YOUR_TOKEN"
CAMPAIGN_ID="YOUR_CAMPAIGN_ID" # Replace with an actual campaign ID
curl -X GET "https://YOUR_API_HOST/link_building/campaigns/$CAMPAIGN_ID" \
  -H "Authorization: Bearer $TOKEN"
```

### 14. Record Outreach Event
Records an event within an outreach campaign (e.g., email sent, reply received).
```bash
TOKEN="YOUR_TOKEN"
CAMPAIGN_ID="YOUR_CAMPAIGN_ID" # Replace with an actual campaign ID
PROSPECT_URL_ENCODED="https%3A%2F%2Fprospectsite.com%2Fcontact"
curl -X POST "https://YOUR_API_HOST/link_building/events" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "campaign_id": "'"$CAMPAIGN_ID"'",
    "prospect_url": "'"$PROSPECT_URL_ENCODED"'",
    "event_type": "email_sent",
    "notes": "Sent initial outreach email.",
    "success": null
  }'
```

### 15. Get Outreach Events for Prospect
Retrieves all outreach events associated with a specific link prospect.
```bash
TOKEN="YOUR_TOKEN"
PROSPECT_URL_ENCODED="https%3A%2F%2Fprospectsite.com%2Fcontact"
curl -X GET "https://YOUR_API_HOST/link_building/prospects/$PROSPECT_URL_ENCODED/events" \
  -H "Authorization: Bearer $TOKEN"
```

### 16. Generate AI Content Ideas
Generates content ideas for a given topic using the AI service.
```bash
TOKEN="YOUR_TOKEN"
curl -X POST "https://YOUR_API_HOST/ai/content_ideas" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "topic": "sustainable living",
    "num_ideas": 3
  }'
```

### 17. Analyze Competitor Strategy with AI
Analyzes competitor strategies using the AI service.
```bash
TOKEN="YOUR_TOKEN"
curl -X POST "https://YOUR_API_HOST/ai/competitor_strategy" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "primary_domain": "yourdomain.com",
    "competitor_domains": ["competitor1.com", "competitor2.com"]
  }'
```

### 18. Get Report Job Status
Retrieves the status of a scheduled or generated report job.
```bash
TOKEN="YOUR_TOKEN"
REPORT_JOB_ID="YOUR_REPORT_JOB_ID" # Replace with an actual report job ID
curl -X GET "https://YOUR_API_HOST/reports/$REPORT_JOB_ID" \
  -H "Authorization: Bearer $TOKEN"
```

### 19. Download Report File
Downloads the generated report file for a completed report job.
```bash
TOKEN="YOUR_TOKEN"
REPORT_JOB_ID="YOUR_REPORT_JOB_ID" # Replace with an actual report job ID
curl -X GET "https://YOUR_API_HOST/reports/$REPORT_JOB_ID/download" \
  -H "Authorization: Bearer $TOKEN" \
  -o "report.pdf" # Or .xlsx depending on format
```

---

## 🩺 Health & System Status Endpoints

### 1. Get API Health Status
Checks the overall health of the API and its dependencies (Redis, PostgreSQL, external services).
```bash
curl -X GET "https://YOUR_API_HOST/health"
```

### 2. Get Prometheus Metrics
Exposes Prometheus-compatible metrics for monitoring.
```bash
curl -X GET "https://YOUR_API_HOST/metrics"
```

### 3. Get System Status
Provides detailed system resource information.
```bash
curl -X GET "https://YOUR_API_HOST/status"
```

---

## 🛠️ Debugging & Admin Endpoints (Requires Admin Privileges)

### 1. Get Dead-Letter Queue Messages
Retrieves messages from the Redis dead-letter queue.
```bash
TOKEN="YOUR_ADMIN_TOKEN" # Requires an admin token
curl -X GET "https://YOUR_API_HOST/debug/dead_letters" \
  -H "Authorization: Bearer $TOKEN"
```

### 2. Clear Dead-Letter Queue
Clears all messages from the Redis dead-letter queue.
```bash
TOKEN="YOUR_ADMIN_TOKEN" # Requires an admin token
curl -X POST "https://YOUR_API_HOST/debug/clear_dead_letters" \
  -H "Authorization: Bearer $TOKEN"
```

### 3. Reprocess Dead-Letter Messages
Moves all messages from the dead-letter queue back to the main job queue for reprocessing.
```bash
TOKEN="YOUR_ADMIN_TOKEN" # Requires an admin token
curl -X POST "https://YOUR_API_HOST/debug/reprocess_dead_letters" \
  -H "Authorization: Bearer $TOKEN"
```

---

## 🖥️ Monitoring Dashboard Endpoints

These endpoints are typically accessed via the web interface at `https://monitor.yspanel.com`, but can also be queried directly.

### 1. Get All Dashboard Statistics
Retrieves all data displayed on the monitoring dashboard.
```bash
curl -X GET "https://YOUR_MONITOR_HOST/api/stats"
```

### 2. Get Satellite Status
Retrieves detailed status of active satellite crawlers.
```bash
curl -X GET "https://YOUR_MONITOR_HOST/api/satellites"
```

### 3. Get Monitoring Dashboard Health
Checks the health of the monitoring dashboard's internal connections (Redis, PostgreSQL, API).
```bash
curl -X GET "https://YOUR_MONITOR_HOST/health"
```
