# 🔗 Link Profiler System

A comprehensive, open-source link analysis and expired domain discovery system inspired by tools like Open Link Profiler and Moz. Built with modern Python async architecture for high-performance web crawling and backlink analysis.

## ✨ Features

### 1. Backlink Data Collection
Our system efficiently discovers and stores detailed backlink information. Each backlink record includes:
*   **`source_url`**: The full URL of the page containing the link.
*   **`target_url`**: The linked-to URL (normalised canonical form).
*   **`anchor_text`**: The text within the `<a>` tag.
*   **`rel_attributes`**: A list of any `rel` values (e.g., `nofollow`, `ugc`, `sponsored`).
*   **`http_status`**: The HTTP response code encountered when fetching the `source_url`.
*   **`crawl_timestamp`**: The UTC timestamp when the `source_url` page was crawled.
*   **`source_domain_metrics`**: Optional enrichment with domain-level data (e.g., estimated domain authority, trust, spam scores) for the source domain.

### 2. SERP Data Acquisition
We capture critical data from Search Engine Results Pages (SERPs) for specified keywords:
*   **`keyword`**: The search term used.
*   **`position`**: The numerical rank in the search results.
*   **`result_url`**: The URL of each result item.
*   **`title_text`**: The page title as displayed in the SERP.
*   **`snippet_text`**: The meta description or snippet text displayed.
*   **`rich_features`**: Flags or details for featured snippets, local packs, images, videos, ads, etc.
*   **`page_load_time`**: Time to fully render the SERP page (optional, from API).
*   **`crawl_timestamp`**: The UTC timestamp of when the search was performed.

### 3. Technical Audit Data
Our system performs page-level technical SEO audits, providing insights into website health and optimisation:
*   **Page-level Metrics**:
    *   **`url`**: The page URL.
    *   **`http_status`**: The HTTP response code.
    *   **`response_time_ms`**: Time to first byte and full load.
    *   **`page_size_bytes`**: Total HTML size.
*   **SEO Checks**:
    *   **`title_length`**: Character count of the `<title>` tag.
    *   **`meta_description_length`**: Character count of the `<meta name="description">` tag.
    *   **`h1_count`**: Number of `<h1>` tags found.
    *   **`broken_links`**: A list of internal/external links on the page returning 4xx/5xx status codes. This is handled by a dedicated **Link Health Auditor** for efficient, batched checks.
    *   Other checks: `internal_links`, `external_links`, `images_count`, `images_without_alt`, `has_canonical`, `has_robots_meta`, `has_schema_markup`, `mobile_friendly` (basic check).
*   **`audit_timestamp`**: The UTC timestamp of when the audit was executed.
*   *(Note: `performance_score` and `accessibility_score` are now populated by Lighthouse integration.)*

### 4. Keyword Research Data
We gather comprehensive data for keyword suggestions:
*   **`seed_keyword`**: The initial term used.
*   **`suggested_keyword`**: Each auto-complete or related suggestion returned.
*   **`search_volume_monthly`**: Estimated monthly search volume.
*   **`cpc_estimate`**: Cost-per-click estimate (if available).
*   **`keyword_trend`**: Monthly interest values (e.g., from Google Trends).
*   **`competition_level`**: Inferred or scraped competition level (Low/Medium/High).
*   **`data_timestamp`**: The UTC timestamp when this data was gathered.

## Architecture Highlights

*   **Modular Design**: Clear separation of concerns with dedicated services (Crawl, Domain, Backlink, SERP, Keyword, Link Health) and crawlers (WebCrawler, LinkExtractor, ContentParser, SERPCrawler, KeywordScraper, TechnicalAuditor).
*   **Asynchronous Operations**: Leverages `asyncio` and `aiohttp` for high-concurrency web requests, ensuring efficient I/O-bound operations.
*   **FastAPI**: Provides a modern, fast (high-performance) web framework for building robust APIs with automatic interactive documentation (Swagger UI).
*   **SQLAlchemy + PostgreSQL**: For robust and scalable data persistence, with ORM models mapping directly to our rich data structures.
*   **Redis**: Used for distributed job queuing, caching (deduplication), and a dead-letter queue for failed jobs.
*   **Background Jobs**: Crawling and auditing tasks run as background jobs, allowing the API to remain responsive.

## 🏗️ Architecture Overview

### **Modular Design**
```
link_profiler/
├── core/                   # Core data models and schemas
│   └── models.py          # Domain, URL, Backlink, LinkProfile models
├── crawlers/              # Web crawling engines
│   ├── web_crawler.py     # Main crawler with rate limiting
│   ├── link_extractor.py  # Extracts links from HTML
│   ├── content_parser.py  # Extracts SEO metrics from content
│   ├── robots_parser.py   # Handles robots.txt fetching and parsing
│   ├── serp_crawler.py    # Playwright-based SERP data extraction
│   ├── keyword_scraper.py # Keyword suggestion and trends scraping
│   └── technical_auditor.py # Lighthouse integration for technical audits
├── services/              # Business logic layer
│   ├── crawl_service.py           # Crawling orchestration
│   ├── domain_service.py          # Domain information retrieval
│   ├── backlink_service.py        # Backlink API integration
│   ├── domain_analyzer_service.py # Domain value analysis
│   ├── expired_domain_finder_service.py # Expired domain discovery
│   ├── serp_service.py            # SERP data service
│   ├── keyword_service.py         # Keyword research service
│   └── link_health_service.py     # Link health auditing
├── database/              # Data persistence layer
│   ├── database.py        # SQLAlchemy ORM for PostgreSQL
│   ├── models.py          # SQLAlchemy ORM models
│   └── clickhouse_loader.py # Bulk loading into ClickHouse
├── api/                   # REST API endpoints
│   ├── main.py            # Main FastAPI application and routes
│   └── queue_endpoints.py # Queue system specific endpoints (integrated into main.py)
├── monitoring/            # Monitoring tools and dashboard
│   ├── dashboard.py       # Web-based monitoring dashboard
│   └── prometheus_metrics.py # Prometheus metrics definitions
├── queue_system/          # Distributed job queue components
│   ├── job_coordinator.py # Central job distribution logic
│   └── satellite_crawler.py # Lightweight worker for executing jobs
├── scripts/               # Utility scripts (e.g., local startup)
├── config/                # Configuration files
└── setup.py              # Project setup and dependencies
```

### **Key Components**

#### **Core Models** (`core/models.py`)
- **Domain**: Authority scores, trust metrics, spam detection
- **URL**: Status tracking, metadata, crawl information  
- **Backlink**: Source/target mapping, anchor text, link types
- **LinkProfile**: Aggregated metrics and analysis results
- **CrawlJob**: Job status, progress tracking, error handling, dead-letter queue integration.
- **SEOMetrics**: Detailed on-page SEO, performance, and accessibility metrics.
- **SERPResult**: Structured data for search engine results.
- **KeywordSuggestion**: Structured data for keyword research.

#### **Web Crawler** (`crawlers/web_crawler.py`)
- Async HTTP client with connection pooling
- Intelligent robots.txt parsing and compliance
- Rate limiting with per-domain tracking
- Content extraction and link discovery
- Error handling and retry logic

#### **Specialised Crawlers/Auditors**
- **SERPCrawler**: Uses Playwright to drive a headless browser for accurate SERP data extraction.
- **KeywordScraper**: Scrapes public keyword suggestion APIs (Google Autocomplete, Bing Suggest) and integrates with Pytrends for trend data.
- **TechnicalAuditor**: Wraps Google Lighthouse CLI to perform comprehensive technical SEO audits (performance, accessibility, best practices).

#### **Business Services**
- **CrawlService**: Orchestrates all types of crawling jobs, manages their state, and persists results.
- **DomainService**: Handles WHOIS lookups and availability checks (supports simulated, AbstractAPI, and real API clients).
- **BacklinkService**: Integrates with external backlink data providers (simulated, OpenLinkProfiler, GSC, or paid APIs).
- **DomainAnalyzerService**: Evaluates domain value and potential.
- **ExpiredDomainFinderService**: Discovers valuable expired domains.
- **LinkHealthService**: Audits outgoing links for brokenness (4xx/5xx errors).
- **SERPService**: Provides an interface for fetching SERP data, prioritising the Playwright crawler or falling back to API clients.
- **KeywordService**: Provides an interface for fetching keyword research data, prioritising the scraper or falling back to API clients.

#### **Data Persistence** (`database/`)
- **PostgreSQL Database**: Used for structured storage of all crawl data, link profiles, and domain information.
- **SQLAlchemy ORM**: Provides an object-relational mapping layer for Python objects to database tables.
- **Upsert Logic**: Ensures data integrity by updating existing records or inserting new ones, preventing duplicate key errors.
- **ClickHouseLoader**: Handles bulk loading of analytical data into ClickHouse for high-performance querying (optional integration).

#### **Distributed Queue System** (`queue_system/`)
- **Redis**: Acts as the central message broker for job queues, results, and heartbeats.
- **JobCoordinator**: The central brain that manages job submission, tracks job status, and monitors satellite health.
- **SatelliteCrawler**: Lightweight, independent worker processes that consume jobs from Redis, execute crawls/audits, and push results back.

#### **Monitoring** (`monitoring/`)
- **Prometheus Metrics**: Exports detailed metrics for API requests, job status, crawler performance, and resource usage, allowing integration with Prometheus and Grafana.
- **Monitoring Dashboard**: A simple web interface to visualise queue status, active satellites, and recent job history.

## 🛠 Installation & Setup

### **Prerequisites**
- Python 3.8+ 
- pip (Python package manager)
- 4GB+ RAM recommended for large crawls
- Stable internet connection
- **Docker and Docker Compose**: Recommended for easy setup of PostgreSQL, Redis, and the distributed components.
- **Node.js and npm**: Required for Lighthouse CLI (installed within Dockerfile.coordinator).
- **Playwright Browsers**: Chromium, Firefox, WebKit (installed within Dockerfile.coordinator and Dockerfile.satellite).

### **Quick Installation (using Docker Compose)**

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/yourusername/Link_Profiler.git
    cd Link_Profiler
    ```

2.  **Build and start Docker services:**
    Navigate to the `Link_Profiler/deployment/docker` directory.
    ```bash
    docker-compose up -d --build
    ```
    This command will:
    *   Build Docker images for `coordinator`, `monitor`, and `satellite` services.
    *   Start PostgreSQL, Redis, the API coordinator, the monitoring dashboard, and three satellite crawlers.

    **Important:** If you plan to use real API clients (e.g., for Domain, Backlink, SERP, Keyword data), you will need to uncomment and set the corresponding environment variables in the `coordinator` service section of `Link_Profiler/deployment/docker/docker-compose.yml`. For example:
    ```yaml
        coordinator:
          # ... other configurations ...
          environment:
            # ... existing environment variables ...
            # - USE_REAL_DOMAIN_API=true
            # - REAL_DOMAIN_API_KEY=your_real_domain_api_key
            # - USE_REAL_SERP_API=true
            # - REAL_SERP_API_KEY=your_real_serp_api_key
            # ... etc.
    ```
    For `USE_GSC_API=true`, ensure your `credentials.json` and `token.json` files are in the project root (`Link_Profiler/`) as described in the "Google Search Console API Setup" section below.

### Google Search Console API Setup (for `GSCBacklinkAPIClient`)

To use the `GSCBacklinkAPIClient`, you need to set up credentials with Google. This involves a few manual steps:

1.  **Create a Google Cloud Project**:
    *   Go to the [Google Cloud Console](https://console.cloud.google.com/).
    *   Create a new project (or select an existing one).

2.  **Enable the Search Console API**:
    *   In the Google Cloud Console, navigate to "APIs & Services" > "Library".
    *   Search for "Google Search Console API" and enable it.

3.  **Create OAuth 2.0 Client ID Credentials**:
    *   In the Google Cloud Console, navigate to "APIs & Services" > "Credentials".
    *   Click "Create Credentials" > "OAuth client ID".
    *   Select "Desktop app" as the application type.
    *   Give it a name (e.g., "Link Profiler GSC Client").
    *   Click "Create".
    *   A dialog will appear with your Client ID and Client Secret. Click "Download JSON".
    *   Rename the downloaded file to `credentials.json` and place it in the root directory of your `Link_Profiler` project (the same directory as `setup.py`).

4.  **Generate `token.json` (First-time Authentication)**:
    *   The `GSCBacklinkAPIClient` will attempt an interactive authentication flow the first time it runs if `token.json` is not found or is invalid.
    *   When you start the API server with `USE_GSC_API="true"` (either via `uvicorn` directly or in `docker-compose.yml`), it will attempt to open a browser window.
    *   Follow the prompts in your browser to authenticate with your Google account and grant the necessary permissions.
    *   After successful authentication, a `token.json` file will be created in your project's root directory. This file stores your access and refresh tokens. **Keep this file secure and do not share it.**
    *   **Important**: This interactive step is not suitable for a headless server environment. For production deployments, you would typically generate `token.json` once on a local machine and then transfer it securely to your server.

## Usage Guide

Once the Docker services are running, the API will be available at: `http://localhost:8000`
-   **API Documentation**: `http://localhost:8000/docs`
-   **Interactive API**: `http://localhost:8000/redoc`
-   **Monitoring Dashboard**: `http://localhost:8001`

### Core API Endpoints

#### 🔍 Backlink Discovery
```bash
# Start a backlink discovery job
POST /crawl/start_backlink_discovery
{
    "target_url": "https://example.com",
    "initial_seed_urls": [
        "https://competitor1.com",
        "https://competitor2.com"
    ],
    "config": {
        "max_depth": 3,
        "max_pages": 1000,
        "delay_seconds": 1.0
    }
}

# Check job status
GET /crawl/status/{job_id}

# Pause a crawl job
POST /crawl/pause/{job_id}

# Resume a crawl job
POST /crawl/resume/{job_id}

# Stop a crawl job
POST /crawl/stop/{job_id}

# Get link profile results
GET /link_profile/https://example.com

# Get raw backlinks
GET /backlinks/https://example.com
```

#### 🔗 Link Health Audit
```bash
# Start a link health audit job for specific source URLs
POST /audit/link_health
{
    "source_urls": [
        "https://www.example.com/page1",
        "https://www.example.com/page2"
    ]
}
```

#### ⚙️ Technical Audit
```bash
# Start a technical audit job for specific URLs using Lighthouse
POST /audit/technical_audit
{
    "urls_to_audit": [
        "https://www.example.com/page1",
        "https://www.example.com/page2"
    ],
    "config": {
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
}
```

#### 📈 SERP Data
```bash
# Fetch SERP data for a keyword
POST /serp/search
{
    "keyword": "best SEO tools",
    "num_results": 20
}

# Get stored SERP results
GET /serp/results/{keyword}
```

#### 💡 Keyword Research
```bash
# Fetch keyword suggestions for a seed keyword
POST /keyword/suggest
{
    "seed_keyword": "content marketing",
    "num_suggestions": 15
}

# Get stored keyword suggestions
GET /keyword/suggestions/{seed_keyword}
```

#### 💎 Domain Analysis
```bash
# Check domain availability
GET /domain/availability/example.com

# Get WHOIS information
GET /domain/whois/example.com

# Get comprehensive domain info
GET /domain/info/example.com

# Analyze domain value
GET /domain/analyze/example.com

# Find expired domains
POST /domain/find_expired_domains
{
    "potential_domains": ["domain1.com", "domain2.com"],
    "min_value_score": 50.0,
    "limit": 100
}
```

#### 📊 Monitoring & Debugging
```bash
# Get Prometheus metrics
GET /metrics

# Get messages from the dead-letter queue
GET /debug/dead_letters

# Clear the dead-letter queue
POST /debug/clear_dead_letters
```

### Configuration Options

#### Crawl Configuration
```python
{
    "max_depth": 3,              # Crawling depth from seed URLs
    "max_pages": 1000,           # Maximum pages to crawl
    "delay_seconds": 1.0,        # Request delay
    "timeout_seconds": 30,       # Request timeout
    "user_agent": "LinkProfiler/1.0",
    "respect_robots_txt": true,  # Honor robots.txt
    "follow_redirects": true,    # Follow HTTP redirects
    "extract_images": true,      # Extract image links
    "extract_pdfs": false,       # Extract PDF documents
    "max_file_size_mb": 10,      # Max download size
    "allowed_domains": [],       # Whitelist domains
    "blocked_domains": [],       # Blacklist domains
    "custom_headers": {}         # Custom HTTP headers
}
```

## Troubleshooting

### Common Issues

#### `psycopg2.OperationalError: FATAL: database "link_profiler_db" does not exist`
-   This means the PostgreSQL database named `link_profiler_db` has not been created. Ensure your Docker PostgreSQL container is running and healthy.

#### "Connection Refused" Errors
-   Check if target websites are accessible.
-   Verify internet connection stability.
-   Reduce concurrent request limits.
-   Increase timeout values.
-   **Check PostgreSQL/Redis Connection**: Ensure your Docker containers for PostgreSQL and Redis are running and accessible.

#### "Robots.txt Blocked" Messages
-   Normal behaviour for sites that restrict crawling.
-   Review robots.txt files manually if needed.
-   Consider alternative seed URLs.
-   Respect website policies.

#### Slow Performance
-   Increase `delay_seconds` to reduce server load.
-   Check available bandwidth and CPU.
-   Monitor memory usage during large crawls.
-   Consider crawling in smaller batches.
-   **Database Performance**: Ensure your PostgreSQL server is adequately resourced and performing well.

#### Out of Memory Errors
-   Reduce `max_pages` limit.
-   Process domains in smaller batches.
-   Monitor system resources.
-   Consider upgrading hardware for large-scale operations.

### API Error Codes
-   **400**: Invalid request parameters or malformed URLs.
-   **404**: Requested resource not found (job, domain, profile).
-   **429**: Rate limit exceeded (reduce request frequency).
-   **500**: Internal server error (check logs for details).
-   **503**: Service unavailable (server overloaded).

## Contributing

Contributions are welcome! Please feel free to open issues or submit pull requests.

## License

This project is licensed under the MIT License.

## Support & Community

### Getting Help
1.  **Documentation**: Check this README and API docs first.
2.  **Issues**: Create GitHub issues for bugs and feature requests.
3.  **Discussions**: Use GitHub Discussions for questions and ideas.
4.  **Code Review**: Submit pull requests for improvements.

### Best Practices
-   Start with small test crawls before large operations.
-   Monitor system resources during intensive operations.
-   Respect website terms of service and robots.txt.
-   Use appropriate delays to avoid overwhelming target servers.
-   Keep backups of important crawl data.

---

**Built by the community for SEO professionals, domain investors, and researchers who need powerful, ethical link analysis tools.**

*Inspired by Open Link Profiler and Moz, built with modern Python for the next generation of SEO analysis.*
