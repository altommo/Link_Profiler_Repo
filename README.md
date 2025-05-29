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
- **Comprehensive Backlink Discovery**: Find all links pointing to target domains
- **Authority Calculation**: Domain and page authority scoring algorithms
- **Spam Detection**: AI-powered spam link identification
- **Anchor Text Analysis**: Detailed anchor text distribution and patterns
- **Link Type Classification**: dofollow, nofollow, sponsored, UGC detection

### 💎 **Expired Domain Discovery**
- **Domain Availability Checking**: Real-time domain registration status
- **Value Assessment**: Multi-factor domain scoring system
- **WHOIS Integration**: Domain age, history, and registration data
- **Batch Processing**: Analyze thousands of domains efficiently
- **Custom Scoring Models**: Configurable domain evaluation criteria

### 📊 **Professional Reporting**
- **Link Profile Generation**: Complete backlink analysis reports
- **Domain Metrics**: Authority, trust, and spam scores
- **SEO Insights**: Technical SEO analysis and recommendations
- **Export Capabilities**: JSON, CSV, and custom report formats
- **Historical Tracking**: Domain and link profile changes over time

### 🚀 **RESTful API**
- **Complete API Coverage**: All features accessible via REST endpoints
- **Real-time Job Tracking**: Monitor crawling progress and status
- **Scalable Architecture**: Designed for high-volume processing
- **Developer Friendly**: Comprehensive OpenAPI documentation
- **Background Processing**: Non-blocking operations with job queues

## 🏗️ Architecture Overview

### **Modular Design**
```
link_profiler/
├── core/                   # Core data models and schemas
│   └── models.py          # Domain, URL, Backlink, LinkProfile models
├── crawlers/              # Web crawling engines
│   └── web_crawler.py     # Main crawler with rate limiting
├── services/              # Business logic layer
│   ├── crawl_service.py           # Crawling orchestration
│   ├── domain_service.py          # Domain information retrieval
│   ├── domain_analyzer_service.py # Domain value analysis
│   └── expired_domain_finder_service.py # Expired domain discovery
├── database/              # Data persistence layer
│   └── database.py        # JSON-based storage (easily replaceable)
├── api/                   # REST API endpoints
│   └── main.py           # FastAPI application and routes
└── main.py               # Application entry point (launcher, not the main app)
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
- **CrawlService**: Orchestrates crawling jobs and manages lifecycles
- **DomainService**: Handles WHOIS lookups and availability checks
- **DomainAnalyzerService**: Evaluates domain value and potential
- **ExpiredDomainFinderService**: Discovers valuable expired domains

## 🛠 Installation & Setup

### **Prerequisites**
- Python 3.8+ 
- pip (Python package manager)
- 4GB+ RAM recommended for large crawls
- Stable internet connection

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

# Create data directory (auto-created on first run)
mkdir -p data
```

### **Dependencies**
```
fastapi          # Modern web framework for APIs
uvicorn[standard] # ASGI server for FastAPI
aiohttp          # Async HTTP client for web crawling
beautifulsoup4   # HTML parsing and link extraction
lxml             # XML/HTML parser (faster than html.parser)
```

## 🚀 Usage Guide

### **Starting the API Server**

To run the API server, you need to ensure that the project's root directory is correctly added to your `PYTHONPATH`. This allows Python to resolve internal package imports.

**Navigate to the project's root directory (where `setup.py` and the `Link_Profiler` package folder are located):**

```bash
cd /path/to/your/Link_Profiler_project_root
```

**Then, activate your virtual environment and run `uvicorn`:**

**For Linux/macOS:**
```bash
source venv/bin/activate
uvicorn Link_Profiler.api.main:app --host 0.0.0.0 --port 8000 --reload
```

**For Windows (Command Prompt):**
```cmd
venv\Scripts\activate
uvicorn Link_Profiler.api.main:app --host 0.0.0.0 --port 8000 --reload
```

**For Windows (PowerShell):**
```powershell
.\venv\Scripts\Activate.ps1
uvicorn Link_Profiler.api.main:app --host 0.0.0.0 --port 8000 --reload
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
    "extract_pdfs": false,       # Extract PDF links
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
- **SEO Value**: Existing search engine presence
- **Commercial Viability**: Market demand and monetization potential

## 🔧 Technical Details

### **Performance Characteristics**
- **Concurrent Requests**: 5-50+ parallel connections
- **Throughput**: 100-1000+ pages per minute (depending on configuration)
- **Memory Usage**: ~50-200MB for typical crawls
- **Storage**: JSON files (~1KB per domain, ~500B per link)
- **Scalability**: Horizontal scaling via multiple instances

### **Rate Limiting & Ethics**
- **Robots.txt Compliance**: Automatically honors crawling restrictions
- **Polite Crawling**: Configurable delays prevent server overload
- **User Agent Identification**: Clear identification as research tool
- **Domain Respect**: Per-domain rate limiting
- **Resource Management**: Automatic connection pooling and cleanup

### **Data Persistence**
- **Storage Format**: JSON files for easy inspection and portability
- **Database Ready**: Modular design allows easy database integration
- **Backup Friendly**: Human-readable data format
- **Version Control**: Data changes can be tracked via Git
- **Migration Path**: Simple upgrade to PostgreSQL/MongoDB

## 🐛 Troubleshooting

### **Common Issues**

#### **"Connection Refused" Errors**
- Check if target websites are accessible
- Verify internet connection stability
- Reduce concurrent request limits
- Increase timeout values

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

### **Planned Features**
- **Database Integration**: PostgreSQL/MongoDB support
- **Advanced Analytics**: Machine learning-based link quality scoring
- **Real-time Monitoring**: Live domain and link change tracking
- **Competitor Analysis**: Side-by-side domain comparisons
- **API Keys & Authentication**: User management and rate limiting
- **Webhook Support**: Real-time notifications for job completion
- **Export Formats**: PDF reports, Excel spreadsheets
- **Historical Data**: Long-term trend analysis and reporting

### **Scalability Improvements**
- **Distributed Crawling**: Multi-server coordination
- **Queue Management**: Redis/RabbitMQ integration
- **Caching Layer**: Redis for frequently accessed data
- **Load Balancing**: Multiple API instances
- **Monitoring**: Prometheus/Grafana dashboards

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
1. **Documentation**: Check this README and API docs first
2. **Issues**: Create GitHub issues for bugs and feature requests
3. **Discussions**: Use GitHub Discussions for questions and ideas
4. **Code Review**: Submit pull requests for improvements

### **Best Practices**
- Start with small test crawls before large operations
- Monitor system resources during intensive operations
- Respect website terms of service and robots.txt
- Use appropriate delays to avoid overwhelming target servers
- Keep backups of important crawl data

---

**Built by the community for SEO professionals, domain investors, and researchers who need powerful, ethical link analysis tools.**

*Inspired by Open Link Profiler and Moz, built with modern Python for the next generation of SEO analysis.*
