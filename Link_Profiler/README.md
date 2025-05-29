# 🔗 Link Profiler System

A comprehensive, open-source link analysis and expired domain discovery system inspired by tools like Open Link Profiler and Moz. Built with modern Python async architecture for high-performance web crawling and backlink analysis.

## ✨ Features

### 🕷️ **Advanced Web Crawling**
- **Asynchronous Architecture**: Built with FastAPI and aiohttp for maximum performance
- **Intelligent Rate Limiting**: Respects robots.txt and implements smart delays
- **Multi-threaded Processing**: Concurrent crawling with configurable limits
- **Robust Error Handling**: Comprehensive retry mechanisms and timeout handling
- **Content Type Support**: HTML, PDF, and image link extraction

### 🔍 **Link Analysis & Profiling**
- **Comprehensive Backlink Discovery**: Find all links pointing to target domains, either by crawling or via external APIs.
- **Authority Calculation**: Domain and page authority scoring algorithms (now more sophisticated, leveraging linking domain metrics).
- **Spam Detection**: AI-powered spam link identification (currently basic).
- **Anchor Text Analysis**: Detailed anchor text distribution and patterns.
- **Link Type Classification**: dofollow, nofollow, sponsored, UGC, redirect, canonical detection.
- **SEO Metrics Extraction**: Extracts and stores on-page SEO data (e.g., title length, heading counts, internal/external links).
- **Backlink API Integration**: Can fetch existing backlink data from external APIs like Google Search Console (for verified properties) and OpenLinkProfiler.org (free, with limits), or a placeholder for paid APIs.

### 💎 **Expired Domain Discovery**
- **Domain Availability Checking**: Real-time domain registration status (now supports real API integration via AbstractAPI's free tier).
- **Value Assessment**: Multi-factor domain scoring system (currently simulated/basic).
- **WHOIS Integration**: Domain age, history, and registration data (now supports real API integration via AbstractAPI's free tier).
- **Batch Processing**: Analyze thousands of domains efficiently.
- **Custom Scoring Models**: Configurable domain evaluation criteria.

### 📊 **Professional Reporting**
- **Link Profile Generation**: Complete backlink analysis reports.
- **Domain Metrics**: Authority, trust, and spam scores.
- **SEO Insights**: Technical SEO analysis and recommendations (extracted and stored).
- **Export Capabilities**: JSON (via API).
- **Historical Tracking**: Domain and link profile changes over time (basic persistence).

### 🚀 **RESTful API**
- **Complete API Coverage**: All features accessible via REST endpoints.
- **Real-time Job Tracking**: Monitor crawling progress and status.
- **Scalable Architecture**: Designed for high-volume processing.
- **Developer Friendly**: Comprehensive OpenAPI documentation.
- **Background Processing**: Non-blocking operations with job queues.

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
│   └── robots_parser.py   # Handles robots.txt fetching and parsing
├── services/              # Business logic layer
│   ├── crawl_service.py           # Crawling orchestration
│   ├── domain_service.py          # Domain information retrieval
│   ├── backlink_service.py        # Backlink API integration
│   ├── domain_analyzer_service.py # Domain value analysis
│   └── expired_domain_finder_service.py # Expired domain discovery
├── database/              # Data persistence layer
│   ├── database.py        # SQLAlchemy ORM for PostgreSQL
│   └── models.py          # SQLAlchemy ORM models
├── api/                   # REST API endpoints
│   └── main.py           # FastAPI application and routes
└── setup.py              # Project setup and dependencies
```

### **Key Components**

#### **Core Models** (`core/models.py`)
- **Domain**: Authority scores, trust metrics, spam detection
- **URL**: Status tracking, metadata, crawl information  
- **Backlink**: Source/target mapping, anchor text, link types
- **LinkProfile**: Aggregated metrics and analysis results
- **CrawlJob**: Job status, progress tracking, error handling

#### **Web Crawler** (`crawlers/web_crawler.py`)
- Async HTTP client with connection pooling
- Intelligent robots.txt parsing and compliance
- Rate limiting with per-domain tracking
- Content extraction and link discovery
- Error handling and retry logic

#### **Business Services**
- **CrawlService**: Orchestrates crawling jobs and manages lifecycles.
- **DomainService**: Handles WHOIS lookups and availability checks (now supports real API integration).
- **BacklinkService**: Integrates with external backlink data providers (simulated, OpenLinkProfiler, GSC, or paid APIs).
- **DomainAnalyzerService**: Evaluates domain value and potential.
- **ExpiredDomainFinderService**: Discovers valuable expired domains.

#### **Data Persistence** (`database/`)
- **PostgreSQL Database**: Used for structured storage of all crawl data, link profiles, and domain information.
- **SQLAlchemy ORM**: Provides an object-relational mapping layer for Python objects to database tables.
- **Upsert Logic**: Ensures data integrity by updating existing records or inserting new ones, preventing duplicate key errors.

## 🛠 Installation & Setup

### **Prerequisites**
- Python 3.8+ 
- pip (Python package manager)
- 4GB+ RAM recommended for large crawls
- Stable internet connection
- **PostgreSQL Database**: Required for data persistence.

### **Quick Installation**
```bash
# Clone the repository
git clone <repository_url>
cd Link_Profiler

# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### **Database Setup (PostgreSQL)**

The application uses a PostgreSQL database for storing crawl data, link profiles, and domain information. You need to have a PostgreSQL server running and create the required database before starting the application.

**For Windows (using PowerShell):**

1.  **Install PostgreSQL**: If you don't have PostgreSQL installed, download and run the installer from the official website: [https://www.postgresql.org/download/windows/](https://www.postgresql.org/download/windows/)
    *   During installation, remember the password you set for the `postgres` superuser.
    *   Ensure the command-line tools (like `psql`) are included in your system's PATH environment variable, or note their installation location (e.g., `C:\Program Files\PostgreSQL\14\bin`).

2.  **Open PowerShell**: Open a new PowerShell window.

3.  **Navigate to PostgreSQL bin directory (if not in PATH)**: If `psql` is not in your PATH, navigate to the `bin` directory of your PostgreSQL installation. **Remember to use double quotes for paths with spaces.** For example:
    ```powershell
    cd "C:\Program Files\PostgreSQL\14\bin" # Adjust version number if needed
    ```

4.  **Connect to PostgreSQL and Create Database**: Use the `psql` command to connect to the default `postgres` database as the `postgres` user and then create the `link_profiler_db`. You will be prompted for the `postgres` user's password.
    ```powershell
    .\psql -U postgres -d postgres -c "CREATE DATABASE link_profiler_db;"
    ```
    *   `-U postgres`: Specifies the user to connect as (`postgres`).
    *   `-d postgres`: Specifies the initial database to connect to (`postgres` is the default).
    *   `-c "CREATE DATABASE link_profiler_db;"`: Executes the SQL command to create the new database.

5.  **Verify Database Creation**: You can optionally connect to the newly created database to verify it exists:
    ```powershell
    .\psql -U postgres -d link_profiler_db
    ```
    If the connection is successful, you will see the `link_profiler_db=#` prompt. Type `\q` and press Enter to exit `psql`.

The application is configured to connect to `postgresql://postgres:postgres@localhost:5432/link_profiler_db` by default. If your PostgreSQL setup uses a different username, password, host, or port, you will need to update the `db_url` parameter in the `Link_Profiler/database/database.py` file or configure it via environment variables (a future enhancement).

### **API Key Setup for External Services**

To use the real API integrations, you will need to obtain API keys and set them as environment variables.

1.  **AbstractAPI (for Domain Info)**:
    *   Go to [AbstractAPI](https://www.abstractapi.com/api/domain-api).
    *   Sign up for a free account to get your API key.
    *   Set the environment variable: `ABSTRACT_API_KEY="your_abstract_api_key_here"`

2.  **Google Search Console API (for Backlinks to Owned Properties)**:
    *   Follow the detailed steps in the "Google Search Console API Setup" section below to create a Google Cloud Project, enable the API, create OAuth 2.0 credentials (`credentials.json`), and generate your `token.json` file.

### **Google Search Console API Setup (for `GSCBacklinkAPIClient`)**

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
    *   When you start the API server with `USE_GSC_API="true"`, it will attempt to open a browser window.
    *   Follow the prompts in your browser to authenticate with your Google account and grant the necessary permissions.
    *   After successful authentication, a `token.json` file will be created in your project's root directory. This file stores your access and refresh tokens. **Keep this file secure and do not share it.**
    *   **Important**: This interactive step is not suitable for a headless server environment. For production deployments, you would typically generate `token.json` once on a local machine and then transfer it securely to your server.

### **Dependencies**
```
fastapi          # Modern web framework for APIs
uvicorn[standard] # ASGI server for FastAPI
aiohttp          # Async HTTP client for web crawling
beautifulsoup4   # HTML parsing and link extraction
lxml             # XML/HTML parser (faster than html.parser)
SQLAlchemy       # SQL toolkit and Object-Relational Mapper
psycopg2-binary  # PostgreSQL adapter for Python
google-api-python-client # Google API client library
google-auth-oauthlib # Google authentication library for OAuth 2.0
```

## 🚀 Usage Guide

### **Starting the API Server**

To run the API server, you need to ensure that the project's root directory is added to your `PYTHONPATH`. This allows Python to correctly resolve internal package imports.

**From the project root directory (where `setup.py` is located):**

**For Linux/macOS:**
```bash
export PYTHONPATH=$(pwd)
# To use the simulated APIs (default):
uvicorn Link_Profiler.api.main:app --host 0.0.0.0 --port 8000 --reload

# To use AbstractAPI for Domain Info (requires ABSTRACT_API_KEY env var):
# export USE_ABSTRACT_API="true"
# export ABSTRACT_API_KEY="your_abstract_api_key_here"
# uvicorn Link_Profiler.api.main:app --host 0.0.0.0 --port 8000 --reload

# To use OpenLinkProfiler.org API for Backlinks (no API key needed):
# export USE_OPENLINKPROFILER_API="true"
# uvicorn Link_Profiler.api.main:app --host 0.0.0.0 --port 8000 --reload

# To use Google Search Console API for Backlinks (requires credentials.json and token.json):
# export USE_GSC_API="true"
# uvicorn Link_Profiler.api.main:app --host 0.0.0.0 --port 8000 --reload

# You can combine domain and backlink API usage, e.g.:
# export USE_ABSTRACT_API="true"
# export ABSTRACT_API_KEY="your_abstract_api_key_here"
# export USE_OPENLINKPROFILER_API="true"
# uvicorn Link_Profiler.api.main:app --host 0.0.0.0 --port 8000 --reload
```

**For Windows (Command Prompt):**
```cmd
set PYTHONPATH=%cd%
rem To use the simulated APIs (default):
uvicorn Link_Profiler.api.main:app --host 0.0.0.0 --port 8000 --reload

rem To use AbstractAPI for Domain Info (requires ABSTRACT_API_KEY env var):
rem set USE_ABSTRACT_API="true"
rem set ABSTRACT_API_KEY="your_abstract_api_key_here"
rem uvicorn Link_Profiler.api.main:app --host 0.0.0.0 --port 8000 --reload

rem To use OpenLinkProfiler.org API for Backlinks (no API key needed):
rem set USE_OPENLINKPROFILER_API="true"
rem uvicorn Link_Profiler.api.main:app --host 0.0.0.0 --port 8000 --reload

rem To use Google Search Console API for Backlinks (requires credentials.json and token.json):
rem set USE_GSC_API="true"
rem uvicorn Link_Profiler.api.main:app --host 0.0.0.0 --port 8000 --reload

rem You can combine domain and backlink API usage, e.g.:
rem set USE_ABSTRACT_API="true"
rem set ABSTRACT_API_KEY="your_abstract_api_key_here"
rem set USE_OPENLINKPROFILER_API="true"
rem uvicorn Link_Profiler.api.main:app --host 0.0.0.0 --port 8000 --reload
```

**For Windows (PowerShell):**
```powershell
$env:PYTHONPATH = (Get-Location).Path
# To use the simulated APIs (default):
uvicorn Link_Profiler.api.main:app --host 0.0.0.0 --port 8000 --reload

# To use AbstractAPI for Domain Info (requires ABSTRACT_API_KEY env var):
# $env:USE_ABSTRACT_API = "true"
# $env:ABSTRACT_API_KEY = "your_abstract_api_key_here"
# uvicorn Link_Profiler.api.main:app --host 0.0.0.0 --port 8000 --reload

# To use OpenLinkProfiler.org API for Backlinks (no API key needed):
# $env:USE_OPENLINKPROFILER_API = "true"
# uvicorn Link_Profiler.api.main:app --host 0.0.0.0 --port 8000 --reload

# To use Google Search Console API for Backlinks (requires credentials.json and token.json):
# $env:USE_GSC_API = "true"
# uvicorn Link_Profiler.api.main:app --host 0.0.0.0 --port 8000 --reload

# You can combine domain and backlink API usage, e.g.:
# $env:USE_ABSTRACT_API = "true"
# $env:ABSTRACT_API_KEY = "your_abstract_api_key_here"
# $env:USE_OPENLINKPROFILER_API = "true"
# uvicorn Link_Profiler.api.main:app --host 0.0.0.0 --port 8000 --reload
```

The API will be available at: `http://localhost:8000`
- **API Documentation**: `http://localhost:8000/docs`
- **Interactive API**: `http://localhost:8000/redoc`

### **Core API Endpoints**

#### **🔍 Backlink Discovery**
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

# Get link profile results
GET /link_profile/https://example.com

# Get raw backlinks
GET /backlinks/https://example.com
```

#### **💎 Domain Analysis**
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

### **Configuration Options**

#### **Crawl Configuration**
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

## 📊 Data Models & Scoring

### **Domain Authority Calculation**
The system uses a multi-factor algorithm:
- **Backlink Quality**: Domain authority of linking sites
- **Link Diversity**: Number of unique referring domains
- **Content Relevance**: Topical relationship analysis
- **Trust Signals**: HTTPS, domain age, clean WHOIS
- **Spam Indicators**: Link patterns, anchor text over-optimization

### **Link Profile Metrics**
- **Total Backlinks**: Raw count of all discovered links
- **Unique Domains**: Number of different referring domains
- **Authority Score**: 0-100 scale based on link quality
- **Trust Score**: 0-100 scale based on clean link sources
- **Spam Score**: 0-100 scale indicating potentially harmful links
- **Anchor Text Distribution**: Keyword usage patterns

### **Domain Value Assessment**
For expired domain discovery:
- **Historical Authority**: Previous domain strength metrics
- **Backlink Profile Quality**: Clean, relevant link sources
- **Brand Potential**: Memorable, brandable domain names
- **SEO Value**: Existing search console presence
- **Commercial Viability**: Market demand and monetization potential

## 🔧 Technical Details

### **Performance Characteristics**
- **Concurrent Requests**: 5-50+ parallel connections
- **Throughput**: 100-1000+ pages per minute (depending on configuration)
- **Memory Usage**: ~50-200MB for typical crawls
- **Storage**: PostgreSQL Database for structured, queryable data.
- **Scalability**: Horizontal scaling via multiple instances

### **Rate Limiting & Ethics**
- **Robots.txt Compliance**: Automatically honors crawling restrictions
- **Polite Crawling**: Configurable delays prevent server overload
- **User Agent Identification**: Clear identification as research tool
- **Domain Respect**: Per-domain rate limiting
- **Resource Management**: Automatic connection pooling and cleanup

### **Data Persistence**
- **Storage Format**: **PostgreSQL Database** for structured, queryable data.
- **Backup Friendly**: Standard database backup procedures apply.
- **Version Control**: Schema changes managed via SQLAlchemy models.

## 🐛 Troubleshooting

### **Common Issues**

#### **`psycopg2.OperationalError: FATAL: database "link_profiler_db" does not exist`**
- This means the PostgreSQL database named `link_profiler_db` has not been created. Follow the "Database Setup (PostgreSQL)" instructions above to create it.

#### **"Connection Refused" Errors**
- Check if target websites are accessible
- Verify internet connection stability
- Reduce concurrent request limits
- Increase timeout values
- **Check PostgreSQL Connection**: Ensure your PostgreSQL server is running and accessible at `localhost:5432` (or the configured address/port). Verify the username and password in `database.py` match your PostgreSQL setup.

#### **"Robots.txt Blocked" Messages**
- Normal behavior for sites that restrict crawling
- Review robots.txt files manually if needed
- Consider alternative seed URLs
- Respect website policies

#### **Slow Performance**
- Increase `delay_seconds` to reduce server load
- Check available bandwidth and CPU
- Monitor memory usage during large crawls
- Consider crawling in smaller batches
- **Database Performance**: Ensure your PostgreSQL server is adequately resourced and performing well.

#### **Out of Memory Errors**
- Reduce `max_pages` limit
- Process domains in smaller batches
- Monitor system resources
- Consider upgrading hardware for large-scale operations

### **API Error Codes**
- **400**: Invalid request parameters or malformed URLs
- **404**: Requested resource not found (job, domain, profile)
- **429**: Rate limit exceeded (reduce request frequency)
- **500**: Internal server error (check logs for details)
- **503**: Service unavailable (server overloaded)

## 🔮 Roadmap & Future Enhancements

The project has a solid foundation with core crawling, link analysis, and domain assessment capabilities. Future development will focus on enhancing these features, improving scalability, and integrating with real-world data sources.

#### **Immediate Next Steps (High Priority)**

1.  **Refine Link Profile Calculation**:
    *   **Completed**: The `authority_score`, `trust_score`, and `spam_score` in `LinkProfile` are now calculated based on the metrics of linking domains.
2.  **Integrate SEO Metrics into Crawl Flow**:
    *   **Completed**: `ContentParser` extracts SEO metrics, and `CrawlService` now persists this data via `Database.save_seo_metrics`.
3.  **Implement Real Domain API Integration**:
    *   **Completed**: The `DomainService` can now be configured to use `AbstractDomainAPIClient` (free tier available) for WHOIS and availability.
4.  **Implement Real Backlink API Integration**:
    *   **Completed**: The `CrawlService` now attempts to fetch backlinks from a `BacklinkService` (which can use `SimulatedBacklinkAPIClient`, `RealBacklinkAPIClient`, `OpenLinkProfilerAPIClient`, or `GSCBacklinkAPIClient` based on environment variables) before or in conjunction with crawling.
    *   **Next Action**:
        *   **OpenLinkProfiler.org Integration**: The `OpenLinkProfilerAPIClient` now makes actual API calls and parses the response.
        *   **GSC API Enhancement**: The `GSCBacklinkAPIClient` now makes actual GSC API calls to fetch top linking sites for verified properties. Ensure `credentials.json` is correctly set up and `token.json` is generated via the interactive OAuth flow for your verified properties.
        *   **Paid API Integration (Optional)**: If a paid API (e.g., Ahrefs, Moz) is acquired, replace the simulated data in `RealBacklinkAPIClient` with actual API calls and response parsing.

#### **Mid-Term Enhancements**

1.  **Advanced Crawl Management**:
    *   Add API endpoints and internal logic to pause, resume, and stop active crawl jobs gracefully.
    *   Implement a job queue system (e.g., using Redis and Celery) for more robust background task management and distributed processing.
2.  **Comprehensive Error Reporting**:
    *   Enhance `CrawlJob`'s `error_log` to capture more structured and actionable error details during crawling.
    *   Implement a mechanism to retry failed URLs or segments of a crawl.
3.  **User Interface / Dashboard**:
    *   Develop a simple web-based UI to interact with the FastAPI endpoints, visualise crawl progress, link profiles, and domain analysis results.
4.  **Competitor Backlink Analysis**:
    *   Add API endpoints and logic to perform link intersect analysis (find common backlinks between domains) and unique backlink discovery.

#### **Long-Term Vision**

1.  **Distributed Crawling Architecture**:
    *   Enable the crawler to run across multiple machines or containers for large-scale data collection.
    *   Implement a robust message queue (e.g., RabbitMQ, Kafka) for inter-service communication and task distribution.
2.  **Machine Learning for Link Quality**:
    *   Develop ML models to predict link quality, spam likelihood, and domain value based on a wider array of features.
3.  **Real-time Monitoring & Alerts**:
    *   Integrate with monitoring tools (e.g., Prometheus, Grafana) to track crawler performance, API health, and database metrics.
    *   Implement webhook support for real-time notifications on job completion or critical errors.
4.  **Authentication & User Management**:
    *   Add API key management and user authentication for secure access to the system.
5.  **Advanced Reporting & Export**:
    *   Generate professional PDF reports, Excel spreadsheets, and other custom export formats for analysis results.

## 🤝 Contributing

We welcome contributions! Areas where you can help:

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
