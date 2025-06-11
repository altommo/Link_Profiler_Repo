# Link Profiler API Documentation v2.0

## 🚀 **Cache-First Architecture**

Link Profiler API delivers **sub-second response times** with our revolutionary cache-first architecture. Unlike traditional SEO APIs that hit live data sources for every request, our system intelligently serves cached data by default while offering live data when you need it.

### **Why Cache-First?**
- **⚡ 10x Faster**: Sub-500ms responses vs 5-15 seconds for live data
- **🛡️ 99.9% Uptime**: Cached responses never fail due to external API issues  
- **💰 Cost Effective**: Cached requests don't count toward your quota
- **🎯 Smart**: Live data available when you need the absolute latest information

---

## 🔐 **Authentication**

All API endpoints require JWT authentication via Bearer token.

### **Get Access Token**
```http
POST /token
Content-Type: application/x-www-form-urlencoded

username=your_username&password=your_password
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

### **Using the Token**
```http
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

---

## 📊 **Subscription Tiers & Access Control**

| Feature | Free | Basic | Pro | Enterprise |
|---------|------|-------|-----|------------|
| **Cached Data** | ✅ | ✅ | ✅ | ✅ |
| **Live Data** | ❌ | ✅ Limited | ✅ Full | ✅ Full |
| **API Calls/Month** | 1,000 | 10,000 | 100,000 | 1,000,000 |
| **Live Calls/Month** | 0 | 100 | 10,000 | 100,000 |
| **Premium Features** | ❌ | ❌ | ✅ | ✅ |

---

## 🛠️ **Core Parameters**

### **Source Parameter**
Every endpoint supports the `source` parameter for data freshness control:

```http
GET /api/domains/example.com/overview?source=cache    # Default: Fast cached data
GET /api/domains/example.com/overview?source=live     # Live data (requires paid plan)
```

**Source Options:**
- `cache` (default): Returns cached data (sub-second response, doesn't count toward quota)
- `live`: Returns real-time data (5-15 second response, requires appropriate tier)

---

## 🏗️ **Phase 1: Core Domain Endpoints**

### **Domain Overview**
Get comprehensive domain analysis including authority metrics, health scores, and key insights.

```http
GET /api/domains/{domain}/overview
```

**Parameters:**
- `domain` (required): Domain to analyze (e.g., "example.com")
- `source` (optional): Data source - `cache` (default) or `live`

**Example Request:**
```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
  "https://api.linkprofiler.com/api/domains/ahrefs.com/overview?source=cache"
```

**Example Response:**
```json
{
  "domain": "ahrefs.com",
  "authority_score": 91,
  "trust_score": 0.89,
  "spam_score": 0.02,
  "total_backlinks": 1284567,
  "referring_domains": 89234,
  "organic_keywords": 456789,
  "estimated_traffic": 2500000,
  "last_updated": "2025-01-15T10:30:00Z",
  "data_source": "cache",
  "seo_metrics": {
    "domain_authority": 91,
    "page_authority": 88,
    "trust_flow": 89,
    "citation_flow": 84,
    "organic_traffic": 2500000,
    "performance_score": 96
  }
}
```

### **Domain Backlinks**
Retrieve backlinks pointing to a domain with detailed metrics.

```http
GET /api/domains/{domain}/backlinks
```

**Example Request:**
```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
  "https://api.linkprofiler.com/api/domains/semrush.com/backlinks?source=cache&limit=100"
```

**Example Response:**
```json
{
  "backlinks": [
    {
      "source_url": "https://blog.hubspot.com/seo-tools-guide",
      "target_url": "https://semrush.com",
      "source_domain": "hubspot.com",
      "anchor_text": "SEMrush competitor analysis",
      "link_type": "dofollow",
      "source_domain_authority": 95,
      "first_seen": "2024-11-15T08:20:00Z",
      "last_seen": "2025-01-14T16:45:00Z",
      "context_text": "For comprehensive competitor analysis, we recommend SEMrush competitor analysis features..."
    }
  ],
  "total_backlinks": 892345,
  "unique_referring_domains": 67234,
  "data_source": "cache",
  "last_updated": "2025-01-15T10:30:00Z"
}
```

### **Domain Metrics**
Get detailed SEO metrics and scores for a domain.

```http
GET /api/domains/{domain}/metrics
```

**Example Response:**
```json
{
  "domain": "moz.com",
  "metrics": {
    "domain_authority": 93,
    "page_authority": 89,
    "spam_score": 0.01,
    "trust_flow": 91,
    "citation_flow": 87,
    "organic_keywords": 234567,
    "estimated_organic_traffic": 1200000,
    "total_backlinks": 567890,
    "referring_domains": 45678,
    "performance_score": 94,
    "mobile_friendly": true,
    "page_speed_score": 89
  },
  "data_source": "cache",
  "last_updated": "2025-01-15T09:15:00Z"
}
```

### **Domain Competitors**
Identify top organic search competitors for a domain.

```http
GET /api/domains/{domain}/competitors
```

**Example Response:**
```json
{
  "primary_domain": "ahrefs.com",
  "competitors": [
    {
      "domain": "semrush.com",
      "competitive_score": 0.89,
      "common_keywords": 15678,
      "avg_position": 3.2,
      "estimated_traffic": 2100000
    },
    {
      "domain": "moz.com", 
      "competitive_score": 0.76,
      "common_keywords": 12456,
      "avg_position": 4.1,
      "estimated_traffic": 980000
    }
  ],
  "data_source": "cache",
  "analysis_date": "2025-01-15T10:30:00Z"
}
```

---

## 🔍 **Phase 2: Analysis Endpoints**

### **SEO Audit**
Comprehensive technical SEO audit with actionable insights.

```http
GET /api/domains/{domain}/seo-audit
```

**Example Response:**
```json
{
  "domain": "example.com",
  "seo_score": 78,
  "audit_results": {
    "technical": {
      "score": 85,
      "issues": [
        {
          "type": "warning",
          "message": "5 pages missing meta descriptions",
          "impact": "medium",
          "recommendation": "Add unique meta descriptions to improve click-through rates"
        }
      ]
    },
    "content": {
      "score": 72,
      "duplicate_content": 3,
      "thin_content_pages": 8,
      "recommendations": ["Expand content on product pages", "Remove duplicate blog posts"]
    },
    "performance": {
      "score": 91,
      "page_speed": 2.1,
      "core_web_vitals": "good"
    }
  },
  "data_source": "cache",
  "audit_timestamp": "2025-01-15T10:30:00Z"
}
```

### **Content Gap Analysis**
Identify content opportunities by comparing against competitors.

```http
POST /api/domains/{domain}/content-gaps
Content-Type: application/json

{
  "competitor_domains": ["competitor1.com", "competitor2.com"]
}
```

**Example Response:**
```json
{
  "target_domain": "yoursite.com",
  "competitor_domains": ["competitor1.com", "competitor2.com"],
  "content_gaps": {
    "missing_topics": [
      "Advanced SEO techniques",
      "Link building automation",
      "Content marketing ROI"
    ],
    "missing_keywords": [
      {
        "keyword": "seo automation tools",
        "search_volume": 5400,
        "difficulty": 67,
        "competitor_ranking": "competitor1.com"
      }
    ],
    "content_format_gaps": ["Video tutorials", "Interactive tools", "Case studies"],
    "actionable_insights": [
      "Create video content for 'SEO tutorial' keywords",
      "Develop interactive SEO calculators",
      "Publish detailed case studies with metrics"
    ]
  },
  "data_source": "cache",
  "analysis_date": "2025-01-15T10:30:00Z"
}
```

### **Keyword Analysis**
Comprehensive keyword research with trends and suggestions.

```http
GET /api/keywords/{keyword}/analysis
```

**Example Request:**
```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
  "https://api.linkprofiler.com/api/keywords/seo%20tools/analysis?source=cache"
```

**Example Response:**
```json
{
  "keyword": "seo tools",
  "analysis": {
    "search_volume": 49500,
    "keyword_difficulty": 76,
    "cpc": 12.45,
    "competition": 0.89,
    "trend_data": [45000, 47000, 49500, 51000, 48500],
    "related_keywords": [
      {
        "keyword": "best seo tools",
        "search_volume": 18100,
        "difficulty": 72,
        "relevance": 0.95
      },
      {
        "keyword": "free seo tools",
        "search_volume": 22200,
        "difficulty": 68,
        "relevance": 0.91
      }
    ],
    "serp_features": ["Featured snippet", "People also ask", "Video results"],
    "seasonality": {
      "peak_months": ["January", "September"],
      "trend_direction": "stable"
    }
  },
  "data_source": "cache",
  "last_updated": "2025-01-15T10:30:00Z"
}
```

### **Keyword Competitors**
Identify top-ranking domains for specific keywords.

```http
GET /api/keywords/{keyword}/competitors
```

**Example Response:**
```json
{
  "keyword": "backlink analysis",
  "top_competitors": [
    {
      "domain": "ahrefs.com",
      "position": 1,
      "url": "https://ahrefs.com/backlink-checker",
      "title": "Free Backlink Checker | Ahrefs",
      "estimated_traffic": 125000,
      "domain_authority": 91
    },
    {
      "domain": "semrush.com", 
      "position": 2,
      "url": "https://semrush.com/backlink-analytics/",
      "title": "Backlink Analytics Tool | SEMrush", 
      "estimated_traffic": 89000,
      "domain_authority": 94
    }
  ],
  "serp_analysis": {
    "avg_domain_authority": 85.3,
    "avg_page_authority": 78.1,
    "content_types": ["Tool pages", "Blog posts", "Landing pages"]
  },
  "data_source": "cache",
  "analysis_date": "2025-01-15T10:30:00Z"
}
```

---

## 🚀 **Phase 3: Advanced Features**

### **Link Prospects**
AI-powered link building prospect identification.

```http
GET /api/domains/{domain}/link-prospects
```

**Access:** Pro and Enterprise plans only

**Example Response:**
```json
{
  "target_domain": "yoursite.com",
  "prospects": [
    {
      "id": "lp_001",
      "prospect_url": "https://techblog.example.com/seo-trends-2025",
      "domain": "techblog.example.com",
      "domain_authority": 72,
      "relevance_score": 0.91,
      "contact_probability": 0.78,
      "estimated_value": "high",
      "contact_info": {
        "email": "editor@techblog.example.com",
        "contact_method": "content_pitch"
      },
      "context": "Article about SEO trends mentions tools like yours",
      "pitch_angle": "Expert quote on future of technical SEO"
    }
  ],
  "total_prospects": 156,
  "data_source": "live",
  "analysis_date": "2025-01-15T11:00:00Z"
}
```

### **Custom Analysis**
Trigger custom domain analysis jobs with specific parameters.

```http
POST /api/domains/{domain}/custom-analysis
Content-Type: application/json

{
  "analysis_type": "deep_crawl_and_audit",
  "config": {
    "max_depth": 5,
    "include_external_links": true,
    "analyze_page_speed": true,
    "check_mobile_usability": true
  }
}
```

**Access:** Pro and Enterprise plans only

**Example Response:**
```json
{
  "job_id": "ca_789123",
  "domain": "example.com",
  "analysis_type": "deep_crawl_and_audit",
  "status": "queued",
  "estimated_completion": "2025-01-15T11:30:00Z",
  "results_url": "/api/reports/ca_789123",
  "config": {
    "max_depth": 5,
    "include_external_links": true,
    "analyze_page_speed": true,
    "check_mobile_usability": true
  }
}
```

### **Report Status**
Check the status of generated reports and download completed analyses.

```http
GET /api/reports/{report_id}
```

**Example Response:**
```json
{
  "id": "ca_789123",
  "report_type": "deep_crawl_and_audit",
  "target_domain": "example.com",
  "status": "completed",
  "created_date": "2025-01-15T11:00:00Z",
  "completed_date": "2025-01-15T11:28:00Z",
  "file_path": "/reports/ca_789123.pdf",
  "download_url": "/api/reports/ca_789123/download",
  "summary": {
    "pages_analyzed": 1247,
    "issues_found": 23,
    "critical_issues": 3,
    "warnings": 12,
    "suggestions": 8
  },
  "data_source": "live"
}
```

---

## 📋 **Tracked Entities Management**

### **Tracked Domains**

#### **Create Tracked Domain**
```http
POST /api/tracked_entities/domains
Content-Type: application/json

{
  "domain_name": "competitor.com",
  "is_active": true
}
```

#### **List Tracked Domains**
```http
GET /api/tracked_entities/domains?source=cache
```

**Example Response:**
```json
{
  "tracked_domains": [
    {
      "id": "td_001",
      "domain_name": "competitor1.com",
      "is_active": true,
      "last_tracked_backlinks": "2025-01-15T08:00:00Z",
      "last_tracked_technical_audit": "2025-01-14T10:00:00Z",
      "last_tracked_gsc_analytics": "2025-01-15T09:30:00Z"
    }
  ],
  "total_domains": 5,
  "data_source": "cache"
}
```

#### **Update Tracked Domain**
```http
PUT /api/tracked_entities/domains/{domain_id}
Content-Type: application/json

{
  "is_active": false,
  "notes": "Pausing tracking temporarily"
}
```

#### **Delete Tracked Domain**
```http
DELETE /api/tracked_entities/domains/{domain_id}
```

### **Tracked Keywords**

#### **Create Tracked Keyword**
```http
POST /api/tracked_entities/keywords
Content-Type: application/json

{
  "keyword": "best seo tools 2025",
  "is_active": true
}
```

#### **List Tracked Keywords**
```http
GET /api/tracked_entities/keywords?source=cache
```

#### **Update/Delete Tracked Keywords**
Similar patterns to tracked domains with appropriate endpoints.

---

## ⚡ **Performance Specifications**

### **Response Times**
- **Cached Data**: < 500ms average, < 200ms p95
- **Live Data**: 5-15 seconds depending on data complexity
- **Bulk Operations**: Optimized for processing multiple requests

### **Rate Limits**
| Tier | Cached Requests | Live Requests | Burst Limit |
|------|----------------|---------------|-------------|
| **Free** | 1000/hour | 0/hour | 50/minute |
| **Basic** | 2500/hour | 100/hour | 100/minute |
| **Pro** | 10000/hour | 1000/hour | 500/minute |
| **Enterprise** | Unlimited | 5000/hour | 2000/minute |

### **Data Freshness**
- **Cached Data**: Updated every 15-30 minutes
- **Live Data**: Real-time from multiple sources
- **Historical Data**: Available for Pro+ plans

---

## 🔄 **API Versioning**

Current version: **v2.0** (Cache-First Architecture)

### **Version Headers**
```http
API-Version: 2.0
Accept: application/json
```

### **Backward Compatibility**
- v1.x endpoints remain supported until December 2025
- Automatic migration tools available for enterprise customers
- v2.0 provides significant performance improvements

---

## 🛠️ **SDK & Integration**

### **Official SDKs**
- **Python**: `pip install linkprofiler-python`
- **Node.js**: `npm install linkprofiler-js`
- **PHP**: `composer require linkprofiler/php-sdk`
- **Ruby**: `gem install linkprofiler`

### **Python Example**
```python
from linkprofiler import LinkProfilerAPI

client = LinkProfilerAPI(api_key="your_api_key")

# Cache-first request (fast)
overview = client.domains.get_overview("ahrefs.com", source="cache")

# Live data request (slower, requires Pro+)
live_backlinks = client.domains.get_backlinks("semrush.com", source="live")

# Bulk operations
domains = ["site1.com", "site2.com", "site3.com"]
results = client.domains.bulk_analysis(domains, source="cache")
```

### **JavaScript Example**
```javascript
const LinkProfiler = require('linkprofiler-js');

const client = new LinkProfiler({ apiKey: 'your_api_key' });

// Async/await with cache-first
const overview = await client.domains.getOverview('moz.com', { source: 'cache' });

// Live data with error handling
try {
  const liveData = await client.domains.getBacklinks('example.com', { 
    source: 'live',
    limit: 1000 
  });
} catch (error) {
  if (error.code === 403) {
    console.log('Live data requires Pro plan upgrade');
  }
}
```

---

## 📊 **Error Handling**

### **HTTP Status Codes**
- `200`: Success
- `400`: Bad Request (invalid parameters)
- `401`: Unauthorized (invalid/missing token)
- `403`: Forbidden (insufficient plan tier for live data)
- `404`: Not Found (domain/resource not found)
- `429`: Too Many Requests (rate limit exceeded)
- `500`: Internal Server Error
- `503`: Service Unavailable (live data temporarily disabled)

### **Error Response Format**
```json
{
  "error": {
    "code": 403,
    "message": "Live data requires Pro plan or higher",
    "details": "Your current Basic plan allows cached data only. Upgrade to access real-time data.",
    "upgrade_url": "https://billing.linkprofiler.com/upgrade",
    "documentation": "https://docs.linkprofiler.com/subscription-tiers"
  },
  "request_id": "req_abc123"
}
```

---

## 🎯 **Best Practices**

### **Optimize Performance**
1. **Use Cached Data by Default**: Get 10x faster responses
2. **Request Live Data Strategically**: Only when you need the absolute latest information
3. **Implement Pagination**: Use `limit` and `offset` parameters for large datasets
4. **Cache Responses Locally**: Implement client-side caching for frequently accessed data

### **Cost Optimization**
1. **Cache-First Approach**: Cached requests don't count toward quotas
2. **Batch Requests**: Use bulk endpoints when analyzing multiple domains
3. **Smart Refresh**: Only request live data when cached data is insufficient
4. **Monitor Usage**: Use webhook notifications for quota alerts

### **Integration Patterns**
```python
# Smart caching pattern
async def get_domain_data(domain, force_live=False):
    source = "live" if force_live else "cache"
    
    try:
        return await client.domains.get_overview(domain, source=source)
    except QuotaExceededError:
        # Fallback to cache if live quota exceeded
        if source == "live":
            return await client.domains.get_overview(domain, source="cache")
        raise
```

---

## 📞 **Support & Resources**

### **Documentation**
- **API Reference**: https://docs.linkprofiler.com/api
- **Tutorials**: https://docs.linkprofiler.com/tutorials
- **Examples**: https://github.com/linkprofiler/api-examples

### **Support Channels**
- **Email**: api-support@linkprofiler.com
- **Chat**: Available in dashboard (Pro+ plans)
- **Status Page**: https://status.linkprofiler.com
- **Community**: https://community.linkprofiler.com

### **SLA & Uptime**
- **Cached Endpoints**: 99.9% uptime guarantee
- **Live Endpoints**: 99.5% uptime (dependent on external sources)
- **Support Response**: < 2 hours for Pro+, < 24 hours for Basic

---

*Link Profiler API v2.0 - Delivering the fastest, most reliable SEO data API in the industry.*