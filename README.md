# 🔗 Link Profiler - Enterprise-Grade Backlink Analysis System

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-13+-blue.svg)](https://www.postgresql.org/)
[![Redis](https://img.shields.io/badge/Redis-6.0+-red.svg)](https://redis.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A comprehensive, open-source link analysis and domain research system inspired by tools like Ahrefs, Moz, and Majestic SEO. Built with modern Python async architecture for high-performance web crawling, backlink analysis, and competitive intelligence.

## 🌟 Key Features

### 🕷️ **Advanced Web Crawling**
- **Asynchronous Architecture**: Built with FastAPI and aiohttp for maximum performance
- **JavaScript Rendering**: Playwright integration for SPA content extraction
- **Intelligent Rate Limiting**: Respects robots.txt and implements adaptive delays
- **Anti-Detection Measures**: User-agent rotation, header randomization, proxy support
- **Content Processing**: HTML, PDF, and image link extraction with OCR capabilities

### 🔍 **Comprehensive Backlink Analysis**
- **Multi-Source Discovery**: Web crawling + API integrations (GSC, Ahrefs, Moz)
- **Link Quality Assessment**: Authority scoring, spam detection, link classification
- **Competitive Analysis**: Link intersect analysis, gap identification
- **Historical Tracking**: Link velocity monitoring, domain authority progression

### 💎 **Domain Intelligence**
- **Domain Research**: WHOIS integration, DNS analysis, availability checking
- **Value Assessment**: Multi-factor domain scoring for expired domains
- **Social Intelligence**: Brand mentions across social media platforms
- **Technical Metrics**: Performance scores, security assessments

### 🤖 **AI-Powered Insights**
- **Content Analysis**: Quality scoring, topic clustering, sentiment analysis
- **Strategic Intelligence**: Competitive gap analysis, content recommendations
- **Link Building**: Automated prospect identification and scoring

### 🛡️ **Enterprise Features**
- **Distributed Processing**: Job coordinator with scalable satellite crawlers
- **Real-time Monitoring**: Prometheus metrics, custom alerts, WebSocket notifications
- **Security**: JWT authentication, role-based access control
- **Deployment Ready**: Docker and Kubernetes configurations

## 🏗️ Architecture Overview

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  FastAPI Server │    │  Job Coordinator │    │ Satellite       │
│  (REST API)     │◄──►│  (Redis Queue)   │◄──►│ Crawlers        │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  PostgreSQL     │    │  Redis Cache     │    │ External APIs   │
│  Database       │    │  & Job Queues    │    │ (GSC, Ahrefs)   │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

### **Modular Design**
The project follows a modular structure to separate concerns and facilitate development.

```
link_profiler/
├── api/                    # FastAPI REST API definitions
│   ├── main.py             # Main FastAPI application entry point
│   ├── routes/             # API endpoint definitions (e.g., admin.py)
│   └── schemas.py          # Pydantic models for API request/response validation
│   └── queue_endpoints.py  # API endpoints for queue management
├── clients/                # Integrations with external services and APIs (e.g., Wayback Machine)
├── config/                 # Configuration loading and management (e.g., config_loader.py)
├── core/                   # Core business logic and data models (e.g., models.py for dataclasses)
├── database/               # Database interaction logic and ORM models (e.g., models.py, clickhouse_loader.py)
├── monitoring/             # Metrics collection and monitoring tools (e.g., crawler_metrics.py)
├── queue_system/           # Task queuing and processing (e.g., smart_crawler_queue.py)
├── static/                 # Static files, including frontend dashboard assets
│   ├── customer-dashboard/ # Customer-facing dashboard assets (e.g., stores, types)
│   └── mission-control-dashboard/ # Mission control dashboard assets (e.g., types)
└── utils/                  # Utility functions and helper classes
    ├── api_cache.py        # Caching for external API responses
    ├── api_rate_limiter.py # Rate limiting for external API calls
    ├── proxy_manager.py    # Proxy management with health checking and rotation
    ├── session_manager.py  # HTTP client session management
    └── user_agent_manager.py # User agent rotation
```

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- PostgreSQL 13+
- Redis 6.0+
- Docker (optional)
- 4GB+ RAM recommended

### 1. Installation

```bash
# Clone the repository
git clone https://github.com/your-org/link-profiler.git
cd link-profiler

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Database Setup

**PostgreSQL Setup:**
```bash
# Create database
createdb link_profiler_db

# Or using psql
psql -U postgres -c "CREATE DATABASE link_profiler_db;"
```

**Redis Setup:**
```bash
# Start Redis server
redis-server

# Or using Docker
docker run -d -p 6379:6379 redis:6-alpine
```

### 3. Configuration

Copy and configure the settings:
```bash
cp .env.example .env
# Edit .env with your database credentials and API keys
```

**Key Configuration Options:**
```yaml
# Database
DATABASE_URL=postgresql://postgres:password@localhost:5432/link_profiler_db

# Redis
REDIS_URL=redis://localhost:6379/0

# External APIs (optional)
ABSTRACT_API_KEY=your_abstract_api_key
GSC_CREDENTIALS_FILE=credentials.json
OPENAI_API_KEY=your_openai_key

# Default Admin User Password (for initial setup)
# This should be set via LP_MONITOR_PASSWORD environment variable
# e.g., LP_MONITOR_PASSWORD=your_secure_admin_password
```

### 4. Start the System

**Option A: Local Development**
```bash
# Set Python path
export PYTHONPATH=$(pwd)

# Start the API server
uvicorn Link_Profiler.main:app --host 0.0.0.0 --port 8000 --reload
```

**Option B: Docker Compose**
```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f
```

### 5. Verify Installation

Visit the API documentation:
- **Interactive API Docs**: http://localhost:8000/docs
- **API Documentation**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/health
- **Prometheus Metrics**: http://localhost:8000/metrics

## 📖 Usage Guide

### Basic Backlink Discovery

```bash
# Start a backlink discovery job
curl -X POST "http://localhost:8000/crawl/start_backlink_discovery" \
  -H "Content-Type: application/json" \
  -d '{
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
  }'

# Check job status
curl "http://localhost:8000/api/queue/job_status/{job_id}"

# Get results
curl "http://localhost:8000/link_profile/https://example.com"
```

### Domain Analysis

```bash
# Check domain availability
curl "http://localhost:8000/domain/availability/example.com"

# Get domain information
curl "http://localhost:8000/domain/info/example.com"

# Analyze domain value
curl "http://localhost:8000/domain/analyze/example.com"
```

### Competitive Analysis

```bash
# Link intersect analysis
curl -X POST "http://localhost:8000/competitive/link_intersect" \
  -H "Content-Type: application/json" \
  -d '{
    "primary_domain": "example.com",
    "competitor_domains": ["competitor1.com", "competitor2.com"]
  }'

# Content gap analysis
curl -X POST "http://localhost:8000/content/gap_analysis" \
  -H "Content-Type: application/json" \
  -d '{
    "target_url": "https://example.com",
    "competitor_urls": ["https://competitor1.com"]
  }'
```

## 🔧 Advanced Configuration

### External API Integrations

**Google Search Console:**
```yaml
backlink_api:
  gsc_api:
    enabled: true
    credentials_file: "credentials.json"
```

**Domain APIs:**
```yaml
domain_api:
  abstract_api:
    enabled: true
    api_key: "your_abstract_api_key"
```

**AI Services:**
```yaml
ai:
  enabled: true
  openrouter_api_key: "your_openrouter_key"
  models:
    content_scoring: "mistralai/mistral-7b-instruct"
```

### Anti-Detection Settings

```yaml
anti_detection:
  user_agent_rotation: true
  request_header_randomization: true
  human_like_delays: true
  stealth_mode: true
  proxy_management: true
```

### Performance Tuning

```yaml
crawler:
  max_depth: 3
  max_pages: 1000
  delay_seconds: 1.0
  max_retries: 3
  timeout_seconds: 30

quality_assurance:
  spam_filtering: true
  data_quality_scoring: true
  anomaly_detection_enabled: true
```

## 🚢 Production Deployment

### Docker Deployment

```bash
# Build and deploy
cd deployment/docker
./deploy.sh

# Scale satellite crawlers
./scale-satellites.sh 5
```

### Kubernetes Deployment

```bash
# Deploy to Kubernetes
cd deployment/kubernetes
./k8s-deploy.sh

# Apply auto-scaling
kubectl apply -f k8s-hpa.yaml
```

### Environment Variables

```bash
# Required
DATABASE_URL=postgresql://user:pass@host:5432/dbname
REDIS_URL=redis://host:6379/0

# Optional
ABSTRACT_API_KEY=your_api_key
GSC_CREDENTIALS_FILE=/path/to/credentials.json
OPENAI_API_KEY=your_openai_key

# Security
JWT_SECRET_KEY=your_super_secret_key
ADMIN_PASSWORD=secure_admin_password
```

## 📊 Monitoring & Observability

### Prometheus Metrics

```
# Job metrics
link_profiler_jobs_total
link_profiler_jobs_duration_seconds
link_profiler_crawled_urls_total

# API metrics
link_profiler_api_requests_total
link_profiler_api_request_duration_seconds

# Cache metrics
link_profiler_cache_hits_total
link_profiler_cache_misses_total
```

### Health Checks

```bash
# System health
curl http://localhost:8000/health

# Database connectivity
curl http://localhost:8000/health/database

# Redis connectivity
curl http://localhost:8000/health/redis

# Queue status
curl http://localhost:8000/api/queue/stats
```

### Alerting

Configure custom alert rules:
```json
{
  "name": "High Error Rate",
  "trigger_type": "metric_threshold",
  "metric_name": "error_rate",
  "threshold_value": 0.1,
  "comparison_operator": ">",
  "severity": "critical",
  "notification_channels": ["webhook", "email"]
}
```

## 🔌 API Reference

### Authentication

```bash
# Register user
curl -X POST "http://localhost:8000/register" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "user",
    "email": "user@example.com",
    "password": "secure_password"
  }'

# Get access token
curl -X POST "http://localhost:8000/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=user&password=secure_password"

# Use token
curl -H "Authorization: Bearer {access_token}" \
  "http://localhost:8000/users/me"
```

### Core Endpoints

**Crawling Operations:**
- `POST /api/queue/submit_crawl` - Submit a new crawl job
- `POST /audit/link_health` - Audit link health
- `POST /audit/technical_audit` - Technical SEO audit
- `GET /api/queue/job_status/{job_id}` - Check job status

**Analysis & Research:**
- `GET /link_profile/{target_url}` - Get link profile
- `GET /backlinks/{target_url}` - Get raw backlinks
- `GET /domain/analyze/{domain}` - Analyze domain
- `POST /competitive/link_intersect` - Link intersect analysis

**SERP & Keywords:**
- `POST /serp/search` - SERP analysis
- `POST /keywords/suggestions` - Keyword research
- `GET /serp/history` - SERP position history

**Advanced Features:**
- `POST /link_building/identify_prospects` - Find link prospects
- `POST /content/gap_analysis` - Content gap analysis
- `POST /ai/topic_clustering` - AI-powered topic clustering

## 🛠️ Development

### Setting Up Development Environment

```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Install pre-commit hooks
pre-commit install

# Run tests
pytest tests/

# Run linting
flake8 Link_Profiler/
black Link_Profiler/

# Type checking
mypy Link_Profiler/
```

### Adding Custom API Clients

1. Create a new client in `clients/`:
```python
class CustomAPIClient(BaseAPIClient):
    async def get_data(self, query: str) -> List[Data]:
        # Implementation
        pass
```

2. Register in configuration:
```yaml
custom_api:
  enabled: true
  api_key: "your_key"
  base_url: "https://api.example.com"
```

3. Integrate in service layer:
```python
# In services/custom_service.py
self.api_client = CustomAPIClient(api_key, base_url)
```

### Custom Crawling Logic

Extend the base crawler:
```python
class CustomCrawler(WebCrawler):
    async def process_custom_content(self, content: str) -> CustomData:
        # Custom processing logic
        pass
```

## 🔍 Troubleshooting

### Common Issues

**Database Connection Issues:**
```bash
# Check PostgreSQL service
sudo systemctl status postgresql

# Test connection
psql -h localhost -U postgres -d link_profiler_db -c "SELECT 1;"
```

**Redis Connection Issues:**
```bash
# Check Redis service
redis-cli ping

# Check memory usage
redis-cli info memory
```

**Crawling Issues:**
```bash
# Check robots.txt compliance
curl http://example.com/robots.txt

# Test with reduced rate limiting
# Set delay_seconds to higher value (e.g., 5.0)
```

**Memory Issues:**
```bash
# Monitor memory usage
docker stats

# Reduce batch sizes in configuration
# Set max_pages to lower value (e.g., 100)
```

### Performance Optimization

**Database:**
```sql
-- Create indexes for better performance
CREATE INDEX idx_backlinks_target_domain ON backlinks(target_domain_name);
CREATE INDEX idx_backlinks_discovered_date ON backlinks(discovered_date);
CREATE INDEX idx_crawl_jobs_status ON crawl_jobs(status);
```

**Redis:**
```bash
# Optimize Redis memory
redis-cli CONFIG SET maxmemory 2gb
redis-cli CONFIG SET maxmemory-policy allkeys-lru
```

**Crawler:**
```yaml
# Optimize crawler settings
crawler:
  max_depth: 2        # Reduce depth for faster crawls
  delay_seconds: 0.5  # Increase speed (be respectful)
  timeout_seconds: 15 # Reduce timeouts
```

### Logging and Debugging

**Enable debug logging:**
```yaml
logging:
  level: DEBUG
```

**View logs:**
```bash
# Docker logs
docker-compose logs -f api

# File logs (if configured)
tail -f logs/link_profiler.log

# Database query logging
# Set sqlalchemy.engine level to INFO in config
```

## 📈 Performance Benchmarks

### Typical Performance Metrics

- **Crawling Speed**: 100-1000+ pages per minute
- **Memory Usage**: 50-200MB for standard crawls
- **Database Throughput**: 1000+ backlinks/second
- **API Response Time**: <100ms for cached queries
- **Concurrent Jobs**: 10-50+ simultaneous crawl jobs

### Scaling Guidelines

**Small Deployment (1-5 users):**
- 2 CPU cores, 4GB RAM
- Single PostgreSQL instance
- Single Redis instance
- 1-2 satellite crawlers

**Medium Deployment (10-50 users):**
- 4-8 CPU cores, 16GB RAM
- PostgreSQL with read replicas
- Redis cluster
- 5-10 satellite crawlers

**Large Deployment (100+ users):**
- 16+ CPU cores, 64GB+ RAM
- PostgreSQL cluster with sharding
- Redis cluster with sentinels
- 20+ satellite crawlers
- Load balancer with multiple API instances

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

### Development Workflow

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Make your changes
4. Add tests for new functionality
5. Run the test suite: `pytest`
6. Commit your changes: `git commit -m 'Add amazing feature'`
7. Push to the branch: `git push origin feature/amazing-feature`
8. Open a Pull Request

### Code Standards

- Follow PEP 8 style guidelines
- Add type hints to all functions
- Write comprehensive docstrings
- Include unit tests for new features
- Update documentation as needed

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

### Getting Help

- **Documentation**: Check this README and API docs
- **Issues**: Create GitHub issues for bugs and feature requests
- **Discussions**: Use GitHub Discussions for questions
- **Email**: support@linkprofiler.dev

### Professional Services

- **Custom Development**: Tailored features and integrations
- **Deployment Support**: Production setup and optimization
- **Training**: Team training and best practices
- **Consulting**: SEO strategy and competitive analysis

## 🔗 Resources

- **API Documentation**: http://localhost:8000/docs
- **Prometheus Metrics**: http://localhost:8000/metrics
- **Health Dashboard**: http://localhost:8001/dashboard
- **Dashboard Templates**: `Link_Profiler/templates` (static assets in `templates/static`)
- **Customer Dashboard**: `customer-dashboard` (React + Vite)
- **Admin Dashboard**: `admin-dashboard` (React + Vite)
- **GitHub Repository**: https://github.com/your-org/link-profiler
- **Docker Hub**: https://hub.docker.com/r/your-org/link-profiler

## 🚧 Current Gaps and Future Work

Based on the provided code and summaries, here are some identified areas that require further development or refinement:

### 1. API Key Management Persistence
- **Gap**: The `POST /admin/api_keys/{api_name}/update` endpoint currently only simulates the update of API keys. Changes are not persisted back to the configuration files or a secure secrets management system.
- **Future Work**: Implement a mechanism within `ConfigLoader` or a dedicated service to securely write updated API keys to a persistent storage (e.g., encrypted configuration file, environment variables, or a secrets manager like HashiCorp Vault).

### 2. Comprehensive Database Integration
- **Gap**: While `Link_Profiler/database/models.py` indicates SQLAlchemy ORM usage and `Link_Profiler/database/clickhouse_loader.py` suggests ClickHouse, the full integration of these with the API endpoints for data storage and retrieval is not fully evident in the provided snippets. Many `core.models.py` dataclasses have `to_dict`/`from_dict` methods, but direct ORM mapping and usage in services are not shown.
- **Future Work**: Ensure all data models are properly mapped to the chosen database(s) (PostgreSQL for transactional data, ClickHouse for analytics/logs) and that API endpoints interact with these databases for persistent storage and retrieval of all relevant data (e.g., crawl results, link profiles, job statuses).

### 3. Full Job Management Lifecycle
- **Gap**: Models for `CrawlJob` and `ReportJob` exist, and `queue_system/smart_crawler_queue.py` defines `CrawlTask`. However, the complete implementation of starting, monitoring, pausing, resuming, and retrieving detailed results for these jobs via dedicated API endpoints (beyond basic status checks) is not fully visible. The actual queueing mechanism (e.g., Redis Queue, Celery) and its integration with the API and satellite crawlers need to be robustly implemented.
- **Future Work**: Develop comprehensive job management services and API endpoints to handle the full lifecycle of crawl and report generation jobs, including error handling, retry mechanisms, and detailed progress reporting.

### 4. Authentication and Authorization
- **Gap**: The `Link_Profiler/api/routes/admin.py` file contains commented-out lines for `get_current_admin_user`, suggesting that authentication and authorization are planned but not yet fully integrated or enforced for administrative endpoints. The `security.yaml` configuration file is mentioned but not provided.
- **Future Work**: Implement robust JWT-based authentication and role-based access control (RBAC) across all API endpoints, ensuring that only authorized users can access sensitive administrative functions and data.

### 5. External API Integrations (Service Layer)
- **Gap**: While API keys are loaded via `ConfigLoader` and `Link_Profiler/clients/wayback_machine_client.py` exists, the actual service layer implementations that utilise these external APIs (e.g., Google Search Console, Ahrefs, Moz, OpenAI, Abstract API) for data enrichment, backlink discovery, or AI-powered insights are not fully detailed in the provided code.
- **Future Work**: Develop dedicated service modules for each external API integration, handling API calls, rate limiting, error handling, and data processing, and integrate these services into the core business logic.

### 6. Monitoring and Metrics Exposure
- **Gap**: `Link_Profiler/monitoring/crawler_metrics.py` defines Prometheus-style metrics. However, the mechanism for exposing these metrics via a dedicated `/metrics` endpoint for Prometheus scraping is not explicitly shown in the provided `api/main.py` or other route files.
- **Future Work**: Implement a `/metrics` endpoint (or similar) to expose the collected Prometheus metrics, allowing for external monitoring and alerting.

### 7. Frontend Integration (Dashboard)
- **Gap**: The `Link_Profiler/static/mission-control-dashboard/src/pages/Settings.tsx` file was removed, indicating that the frontend component for managing API keys might no longer exist or is not integrated. While the backend endpoint `GET /admin/api_keys` is now functional, there might be no active frontend consuming it.
- **Future Work**: Re-evaluate the frontend dashboard strategy. If API key management is a required feature, ensure a corresponding frontend component is developed and properly integrated with the backend API.

### 8. Comprehensive Testing and Deployment Assets
- **Gap**: The `README.md` mentions `pytest` for testing and `docker-compose` / Kubernetes for deployment, but no actual `tests/` directory or `deployment/` assets (e.g., Dockerfiles, Kubernetes manifests) were provided for review.
- **Future Work**: Develop a comprehensive suite of unit, integration, and end-to-end tests. Provide complete and verified Docker and Kubernetes deployment configurations to ensure easy and reliable deployment of the entire system.

## 🚀 Roadmap

### Upcoming Features

- **GraphQL API**: Modern query interface
- **Machine Learning**: Advanced spam detection and quality scoring
- **Real-time Streaming**: WebSocket-based live updates
- **Mobile App**: iOS and Android applications
- **Enterprise SSO**: SAML and OAuth integration
- **Advanced Visualizations**: Interactive link maps and charts

### Integration Priorities

- **Additional APIs**: More backlink and domain data sources
- **CRM Integration**: Salesforce, HubSpot connectors
- **Reporting Tools**: Tableau, Power BI connections
- **Workflow Automation**: Zapier, IFTTT integration

---

**Built with ❤️ by the SEO community for modern digital marketing professionals.**

*Transform your SEO strategy with enterprise-grade backlink intelligence.*
