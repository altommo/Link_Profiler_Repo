# 🔗 Link Profiler System

A comprehensive, open-source link analysis and expired domain discovery system inspired by tools like Open Link Profiler and Moz. Built with modern Python async architecture for high-performance web crawling and backlink analysis.

## ✨ Features

### 🕷️ **Advanced Web Crawling**
- **Asynchronous Architecture**: Built with FastAPI and aiohttp for maximum performance.
- **Intelligent Rate Limiting**: Respects robots.txt and implements smart delays.
- **Distributed Processing**: Leverages a Redis-based job queue with multiple satellite crawlers for horizontal scalability.
- **Robust Error Handling**: Comprehensive retry mechanisms, timeout handling, and a dead-letter queue for failed jobs.
- **Anti-Bot Detection**: User-agent rotation, request header randomization, human-like delays, and Playwright stealth mode.
- **Content Type Support**: HTML, PDF, and image link extraction.
- **Proxy Management**: Rotates and manages a pool of proxies, temporarily blacklisting failed ones.
- **Crawl Job Management**: Ability to pause, resume, and stop active crawl jobs.

### 🔍 **Link Analysis & Profiling**
- **Comprehensive Backlink Discovery**: Find all links pointing to target domains, either by crawling or via external APIs.
- **Authority Calculation**: Domain and page authority scoring algorithms (now more sophisticated, leveraging linking domain metrics).
- **Spam Detection & Quality Filtering**: Configurable filtering of backlinks based on their `SpamLevel` and the quality signals (e.g., low authority, high spam score) of the source domain.
- **Anchor Text Analysis**: Detailed anchor text distribution and patterns.
- **Link Type Classification**: dofollow, nofollow, sponsored, UGC, redirect, canonical detection.
- **SEO Metrics Extraction**: Extracts and stores on-page SEO data (e.g., title length, heading counts, internal/external links, structured data, social meta).
- **Content Validation**: Detects bot-detection indicators, checks content completeness, and flags scraping artifacts.
- **Backlink API Integration**: Can fetch existing backlink data from external APIs like Google Search Console (for verified properties) and OpenLinkProfiler.org (free, with limits), or a placeholder for paid APIs.

### 💎 **Expired Domain Discovery & Analysis**
- **Domain Availability Checking**: Real-time domain registration status (now supports real API integration via AbstractAPI's free tier).
- **Value Assessment**: Multi-factor domain scoring system, enhanced with AI-driven insights.
- **WHOIS Integration**: Domain age, history, and registration data (now supports real API integration via AbstractAPI's free tier).
- **Batch Processing**: Submit lists of domains for analysis to the distributed queue.
- **Custom Scoring Models**: Configurable domain evaluation criteria.

### 📊 **Professional Reporting & Auditing**
- **Link Profile Generation**: Complete backlink analysis reports.
- **Domain Metrics**: Authority, trust, and spam scores.
- **Technical SEO Audits**: Integrates with Google Lighthouse for performance, accessibility, and best practices scores.
- **Link Health Auditing**: Checks for broken outgoing links on specified pages.
- **Keyword Research**: Fetches keyword suggestions and trend data, with optional integration for real search volume and CPC metrics.
- **SERP Analysis**: Extracts data from Search Engine Results Pages for given keywords, with enhanced rich feature detection.
- **Full SEO Audit**: A higher-level job type that orchestrates multiple audit tasks (e.g., technical audit, link health audit) for a given set of URLs.
- **Export Capabilities**: JSON (via API) and CSV for various data types.
- **Historical Tracking**: Domain and link profile changes over time (basic persistence).

### 🚀 **RESTful API**
- **Complete API Coverage**: All features accessible via REST endpoints.
- **Asynchronous Job Submission**: API endpoints submit jobs to a distributed queue, allowing for non-blocking operations.
- **Real-time Job Tracking**: Monitor crawling progress and status via API.
- **Scalable Architecture**: Designed for high-volume processing with distributed workers.
- **Developer Friendly**: Comprehensive OpenAPI documentation.

## 🏗️ Architecture Overview

### **Modular Design**
```
link_profiler/
├── core/                   # Core data models and schemas
│   └── models.py          # Domain, URL, Backlink, LinkProfile models
├── crawlers/              # Web crawling engines
│   ├── web_crawler.py     # Main crawler with rate limiting, proxy, anti-detection
│   ├── link_extractor.py  # Extracts links from HTML
│   ├── content_parser.py  # Extracts SEO metrics from content
│   ├── robots_parser.py   # Handles robots.txt fetching and parsing
│   ├── serp_crawler.py    # Playwright-based SERP data extraction
│   ├── keyword_scraper.py # Keyword suggestion and trends scraping
│   └── technical_auditor.py # Lighthouse integration for technical audits
├── services/              # Business logic layer
│   ├── crawl_service.py           # Crawling orchestration, backlink filtering
│   ├── domain_service.py          # Domain information retrieval
│   ├── backlink_service.py        # Backlink API integration
│   ├── domain_analyzer_service.py # Domain value analysis
│   ├── expired_domain_finder_service.py # Expired domain discovery
│   ├── serp_service.py            # SERP data service
│   ├── keyword_service.py         # Keyword research service
│   ├── link_health_service.py     # Link health auditing
│   └── ai_service.py              # AI integration for content/domain analysis
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
├── utils/                 # General utilities (logging, user agents, proxies, content validation)
│   ├── logging_config.py
│   ├── user_agent_manager.py
│   ├── proxy_manager.py
│   ├── content_validator.py
│   └── data_exporter.py
└── setup.py              # Project setup and dependencies
```

### **Key Components**

#### **Core Models** (`core/models.py`)
- **Domain**: Authority scores, trust metrics, spam detection.
- **URL**: Status tracking, metadata, crawl information.
- **Backlink**: Source/target mapping, anchor text, link types, enriched with source domain metrics.
- **LinkProfile**: Aggregated metrics and analysis results.
- **CrawlJob**: Job status, progress tracking, error handling, dead-letter queue integration, scheduling.
- **SEOMetrics**: Detailed on-page SEO, performance, accessibility, structured data, social meta, and content validation issues.
- **SERPResult**: Structured data for search engine results.
- **KeywordSuggestion**: Structured data for keyword research.

#### **Web Crawler** (`crawlers/web_crawler.py`)
- Async HTTP client with connection pooling.
- Intelligent robots.txt parsing and compliance.
- Adaptive rate limiting with per-domain tracking.
- Content extraction and link discovery.
- Error handling and retry logic.
- Integrates `UserAgentManager` for dynamic headers and `ProxyManager` for IP rotation.
- Uses `ContentValidator` for post-crawl content quality checks.

#### **Specialised Crawlers/Auditors**
- **SERPCrawler**: Uses Playwright to drive a headless browser for accurate SERP data extraction, with refined rich feature detection and anti-detection measures.
- **KeywordScraper**: Scrapes public keyword suggestion APIs (Google Autocomplete, Bing Suggest) and integrates with Pytrends for trend data.
- **TechnicalAuditor**: Wraps Google Lighthouse CLI to perform comprehensive technical SEO audits (performance, accessibility, best practices).

#### **Business Services**
- **CrawlService**: Orchestrates all types of crawling jobs, manages their state, persists results, and applies backlink quality filtering.
- **DomainService**: Handles WHOIS lookups and availability checks (supports simulated, AbstractAPI, and real API clients).
- **BacklinkService**: Integrates with external backlink data providers (simulated, OpenLinkProfiler, GSC, or paid APIs).
- **DomainAnalyzerService**: Evaluates domain value and potential, leveraging AI insights.
- **ExpiredDomainFinderService**: Discovers valuable expired domains.
- **LinkHealthService**: Audits outgoing links for brokenness (4xx/5xx errors).
- **SERPService**: Provides an interface for fetching SERP data, prioritising the Playwright crawler or falling back to API clients.
- **KeywordService**: Provides an interface for fetching keyword research data, prioritising the scraper or falling back to API clients, with optional integration for real search volume and CPC metrics.
- **AIService**: Integrates with OpenRouter for AI-powered content scoring, content gap analysis, semantic keyword suggestions, technical SEO analysis, competitor analysis, and domain value analysis.

#### **Data Persistence** (`database/`)
- **PostgreSQL Database**: Used for structured storage of all crawl data, link profiles, and domain information.
- **SQLAlchemy ORM**: Provides an object-relational mapping layer for Python objects to database tables.
- **Upsert Logic**: Ensures data integrity by updating existing records or inserting new ones, preventing duplicate key errors.
- **ClickHouseLoader**: Handles bulk loading of analytical data into ClickHouse for high-performance querying (optional integration).

#### **Distributed Queue System** (`queue_system/`)
- **Redis**: Acts as the central message broker for job queues, results, and heartbeats.
- **JobCoordinator**: The central brain that manages job submission, tracks job status (from DB), monitors satellite health, and processes scheduled jobs.
- **SatelliteCrawler**: Lightweight, independent worker processes that consume jobs from Redis, execute crawls/audits, and push results back.

#### **Monitoring** (`monitoring/`)
- **Prometheus Metrics**: Exports detailed metrics for API requests, job status, crawler performance, and resource usage, allowing integration with Prometheus and Grafana.
- **Monitoring Dashboard**: A simple web interface to visualise queue status, active satellites, and recent job history (now fetches real data from DB and Redis).

## 🛠 Installation & Setup

### **Prerequisites**
- Python 3.8+ 
- pip (Python package manager)
- 4GB+ RAM recommended for large crawls
- Stable internet connection
- **Docker and Docker Compose**: Recommended for easy setup of PostgreSQL, Redis, and the distributed components.
- **Node.js and npm**: Required for Lighthouse CLI (installed within Dockerfile.coordinator and Dockerfile.satellite).
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
            # - LP_DOMAIN_API_ABSTRACT_API_ENABLED=true
            # - LP_DOMAIN_API_ABSTRACT_API_API_KEY=your_abstract_api_key_here
            # - LP_SERP_API_REAL_API_ENABLED=true
            # - LP_SERP_API_REAL_API_KEY=your_real_serp_api_key
            # ... etc.
    ```
    Note the `LP_` prefix for environment variables, as configured in `Link_Profiler/config/config_loader.py`.
    For `LP_BACKLINK_API_GSC_API_ENABLED=true`, ensure your `credentials.json` and `token.json` files are in the project root (`Link_Profiler/`) as described in the "Google Search Console API Setup" section below.

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
    *   When you start the API server with `LP_BACKLINK_API_GSC_API_ENABLED="true"` (either via `uvicorn` directly or in `docker-compose.yml`), it will attempt to open a browser window.
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
# Submit a backlink discovery job to the queue
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

# Check job status (from database)
GET /crawl/status/{job_id}

# Get all jobs (from database)
GET /crawl/all_jobs

# Pause a crawl job
POST /crawl/pause/{job_id}

# Resume a crawl job
POST /crawl/resume/{job_id}

# Stop a crawl job
POST /crawl/stop/{job_id}

# Get link profile results (from database)
GET /link_profile/https://example.com

# Get raw backlinks (from database)
GET /backlinks/https://example.com
```

#### 🔗 Link Health Audit
```bash
# Submit a link health audit job to the queue
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
# Submit a technical audit job to the queue
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
# Submit a SERP search job to the queue
POST /serp/search
{
    "keyword": "best SEO tools",
    "num_results": 20,
    "search_engine": "google"
}

# Get stored SERP results (from database)
GET /serp/results/{keyword}
```

#### 💡 Keyword Research
```bash
# Submit a keyword suggestion job to the queue
POST /keyword/suggest
{
    "seed_keyword": "content marketing",
    "num_suggestions": 15
}

# Get stored keyword suggestions (from database)
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

# Submit a batch domain analysis job to the queue
POST /domain/analyze_batch
{
    "domain_names": ["domain1.com", "domain2.com"],
    "min_value_score": 50.0,
    "limit": 100
}

# Find expired domains (direct, non-queued operation)
POST /domain/find_expired_domains
{
    "potential_domains": ["domain1.com", "domain2.com"],
    "min_value_score": 50.0,
    "limit": 100
}
```

#### 🚀 Full SEO Audit
```bash
# Submit a full SEO audit job to the queue
POST /audit/full_seo_audit
{
    "urls_to_audit": [
        "https://www.example.com/page1",
        "https://www.example.com/page2"
    ],
    "config": {
        "user_agent": "FullSEOAduitBot/1.0"
    }
}
```

#### 📊 Monitoring & Debugging
```bash
# Get Prometheus metrics
GET /metrics

# Get messages from the Redis dead-letter queue
GET /debug/dead_letters

# Clear the Redis dead-letter queue
POST /debug/clear_dead_letters
```

### Configuration Options

Configuration is loaded from `Link_Profiler/config/default.json`, overridden by `Link_Profiler/config/{ENVIRONMENT}.json` (e.g., `development.json`), and finally by environment variables prefixed with `LP_`.

Example environment variable: `LP_REDIS_URL=redis://my-redis-host:6379` would override `redis.url` in the JSON config.

#### Crawl Configuration (from `Link_Profiler/core/models.py` and JSON config)
```python
{
    "max_depth": 3,              # Crawling depth from seed URLs
    "max_pages": 1000,           # Maximum pages to crawl
    "delay_seconds": 1.0,        # Delay between requests to the same domain in seconds
    "timeout_seconds": 30,       # Timeout for HTTP requests in seconds
    "user_agent": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)", # User-Agent string for the crawler
    "respect_robots_txt": true,  # Whether to respect robots.txt rules (can be overridden by LP_CRAWLER_RESPECT_ROBOTS_TXT)
    "follow_redirects": true,    # Whether to follow HTTP redirects
    "extract_images": true,      # Whether to extract image links
    "extract_pdfs": false,       # Whether to extract links from PDF documents
    "max_file_size_mb": 10,      # Maximum file size to download in MB
    "allowed_domains": [],       # List of domains explicitly allowed to crawl. If empty, all domains are allowed unless blocked.
    "blocked_domains": [],       # List of domains explicitly blocked from crawling.
    "custom_headers": {},        # Custom HTTP headers to send with requests.
    "max_retries": 3,            # Maximum number of retries for failed URL fetches.
    "retry_delay_seconds": 5.0,  # Delay between retries in seconds.
    "user_agent_rotation": false, # Whether to rotate user agents from a pool.
    "request_header_randomization": false, # Whether to randomize other request headers (Accept, Accept-Language, etc.).
    "human_like_delays": false,  # Whether to add small random delays to mimic human browsing behavior.
    "stealth_mode": true,        # Whether to enable Playwright stealth mode for browser-based crawling.
    "use_proxies": false,        # Whether to use proxies for crawling.
    "proxy_list": []             # List of proxy URLs (e.g., 'http://user:pass@ip:port').
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

## 🏁 Roadmap & Future Enhancements

The project has a solid foundation with core crawling, link analysis, and domain assessment capabilities. Future development will focus on enhancing these features, improving scalability, and integrating with real-world data sources.

### **Completed (from previous roadmap)**
- **Comprehensive Error Reporting**: `CrawlJob`'s `error_log` now captures structured error details, and a retry mechanism for failed URLs is implemented.
- **Distributed Crawling Architecture**: Implemented using Redis queues, JobCoordinator, and SatelliteCrawlers.
- **Real-time Monitoring & Alerts**: Prometheus metrics and a basic monitoring dashboard are in place.
- **Technical SEO Audits**: Integrated with Google Lighthouse.
- **SERP Analysis**: Implemented with Playwright and API clients.
- **Keyword Research**: Implemented with a scraper and API clients.
- **Full SEO Audit**: Orchestrates technical and link health audits.
- **AI Integration**: For content scoring, domain value analysis, etc.
- **Proxy Management**: Implemented rotation and blacklisting.
- **Content Validation**: Implemented checks for bot detection and content completeness.
- **Backlink Quality Filtering and Spam Detection**: Implemented configurable filtering based on spam level and source domain quality.
- **Export Capabilities**: CSV export for various data types.

### **Immediate Next Steps (High Priority)**

1.  **User Interface / Dashboard Enhancements**:
    *   Develop a more interactive web-based UI to visualise crawl progress, link profiles, and domain analysis results.
    *   Allow direct submission of jobs and configuration changes from the UI.
2.  **Competitor Backlink Analysis**:
    *   Add API endpoints and logic to perform link intersect analysis (find common backlinks between domains) and unique backlink discovery.

### **Mid-Term Enhancements**

1.  **Advanced Machine Learning for Link Quality**:
    *   Develop more sophisticated ML models to predict link quality, spam likelihood, and domain value based on a wider array of features and historical data.
2.  **Advanced Reporting & Export**:
    *   Generate professional PDF reports, Excel spreadsheets, and other custom export formats for analysis results.
3.  **Authentication & User Management**:
    *   Add API key management and user authentication for secure access to the system.
4.  **Scalability Optimizations**:
    *   Further optimize database queries and data handling for extremely large datasets.
    *   Explore advanced load balancing and auto-scaling strategies for Kubernetes deployments.

## 🤝 Contributing

We welcome contributions! Please feel free to open issues or submit pull requests.

### **Development**
- Additional link analysis algorithms
- New domain scoring models  
- Performance optimizations
- Bug fixes and stability improvements

### **Documentation**
- API usage examples
- Tutorial content
- Architecture documentation
- Troubleshooting guides

### **Testing**
- Unit test coverage
- Integration tests
- Performance benchmarking
- Edge case testing

## 📄 License

This project is open source and available under the MIT License. 

## 🆘 Support & Community

### **Getting Help**
1.  **Documentation**: Check this README and API docs first
2.  **Issues**: Create GitHub issues for bugs and feature requests
3.  **Discussions**: Use GitHub Discussions for questions and ideas
4.  **Code Review**: Submit pull requests for improvements

### **Best Practices**
- Start with small test crawls before large operations
- Monitor system resources during intensive operations
- Respect website terms of service and robots.txt
- Use appropriate delays to avoid overwhelming target servers
- Keep backups of important crawl data

---

**Built by the community for SEO professionals, domain investors, and researchers who need powerful, ethical link analysis tools.**

*Inspired by Open Link Profiler and Moz, built with modern Python for the next generation of SEO analysis.*
