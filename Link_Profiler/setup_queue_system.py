#!/usr/bin/env python3
"""
Automated Setup Script for Link Profiler Queue System
Run this from your Link_Profiler root directory
"""
import os
import sys
import shutil
from pathlib import Path

def create_directory_structure():
    """Create the required directory structure"""
    directories = [
        "Link_Profiler/queue_system",
        "Link_Profiler/deployment/docker", 
        "Link_Profiler/deployment/kubernetes",
        "admin-management-console/static/css",
        "admin-management-console/static/js",
        "Link_Profiler/scripts",
        "Link_Profiler/config",
        "Link_Profiler/core",
        "Link_Profiler/crawlers",
        "Link_Profiler/services",
        "Link_Profiler/database",
        "Link_Profiler/api",
        "Link_Profiler/utils"
    ]
    
    print("📁 Creating directory structure...")
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
        print(f"  ✅ Created: {directory}")
    
    # Create __init__.py files for all packages
    init_files = [
        "Link_Profiler/__init__.py",
        "Link_Profiler/queue_system/__init__.py",
        "Link_Profiler/monitoring/__init__.py",
        "Link_Profiler/core/__init__.py",
        "Link_Profiler/crawlers/__init__.py",
        "Link_Profiler/services/__init__.py",
        "Link_Profiler/database/__init__.py",
        "Link_Profiler/api/__init__.py",
        "Link_Profiler/utils/__init__.py"
    ]
    
    for init_file in init_files:
        Path(init_file).touch()
        print(f"  ✅ Created: {init_file}")

def create_config_files():
    """Create configuration files"""
    print("\n⚙️ Creating configuration files...")
    
    # Default config
    default_config = """{
  "redis": {
    "url": "redis://localhost:6379"
  },
  "database": {
    "url": "postgresql://postgres:postgres@localhost:5432/link_profiler_db"
  },
  "crawler": {
    "max_depth": 3,
    "max_pages": 1000,
    "delay_seconds": 1.0,
    "timeout_seconds": 30,
    "respect_robots_txt": true,
    "follow_redirects": true,
    "extract_images": true,
    "extract_pdfs": false,
    "max_file_size_mb": 10,
    "user_agent_rotation": false
  },
  "anti_detection": {
    "stealth_mode": true,
    "fingerprint_randomization": false,
    "human_like_delays": false,
    "request_header_randomization": false
  },
  "proxy_management": {
    "enabled": false,
    "proxy_list": [],
    "proxy_retry_delay_seconds": 300
  },
  "quality_assurance": {
    "content_validation": false,
    "duplicate_detection": true,
    "spam_filtering": true,
    "data_quality_scoring": true
  },
  "queue": {
    "max_retries": 3,
    "retry_delay": 5,
    "priority_levels": [1, 5, 10],
    "heartbeat_interval": 30,
    "stale_timeout": 60,
    "dead_letter_queue_name": "dead_letter_queue"
  },
  "monitoring": {
    "dashboard_refresh": 30,
    "max_job_history": 100,
    "performance_window": 3600
  },
  "api": {
    "host": "0.0.0.0",
    "port": 8000
  },
  "logging": {
    "level": "INFO",
    "config": {
      "version": 1,
      "disable_existing_loggers": false,
      "formatters": {
        "standard": {
          "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        },
        "detailed": {
          "format": "%(asctime)s - %(name)s:%(lineno)d - %(levelname)s - %(message)s"
        }
      },
      "handlers": {
        "console": {
          "class": "logging.StreamHandler",
          "formatter": "standard",
          "level": "INFO"
        },
        "file": {
          "class": "logging.handlers.RotatingFileHandler",
          "formatter": "detailed",
          "filename": "link_profiler.log",
          "maxBytes": 10485760,
          "backupCount": 5,
          "level": "INFO"
        }
      },
      "loggers": {
        "Link_Profiler": {
          "handlers": ["console", "file"],
          "level": "INFO",
          "propagate": false
        },
        "uvicorn": {
          "handlers": ["console"],
          "level": "INFO",
          "propagate": false
        },
        "uvicorn.access": {
          "handlers": ["console"],
          "level": "INFO",
          "propagate": false
        },
        "sqlalchemy": {
          "handlers": ["console"],
          "level": "WARNING",
          "propagate": false
        },
        "redis": {
          "handlers": ["console"],
          "level": "WARNING",
          "propagate": false
        },
        "playwright": {
          "handlers": ["console"],
          "level": "WARNING",
          "propagate": false
        },
        "pytrends": {
          "handlers": ["console"],
          "level": "WARNING",
          "propagate": false
        },
        "googleapiclient": {
          "handlers": ["console"],
          "level": "WARNING",
          "propagate": false
        }
      },
      "root": {
        "handlers": ["console"],
        "level": "WARNING"
      }
    }
  },
  "domain_api": {
    "abstract_api": {
      "enabled": false,
      "api_key": "your_abstract_api_key_here"
    },
    "real_api": {
      "enabled": false,
      "api_key": "your_real_domain_api_key_here"
    }
  },
  "backlink_api": {
    "gsc_api": {
      "enabled": false
    },
    "openlinkprofiler_api": {
      "enabled": false
    },
    "real_api": {
      "enabled": false,
      "api_key": "your_real_backlink_api_key_here"
    }
  },
  "serp_crawler": {
    "playwright": {
      "enabled": false,
      "headless": true,
      "browser_type": "chromium"
    }
  },
  "serp_api": {
    "real_api": {
      "enabled": false,
      "api_key": "your_real_serp_api_key_here"
    }
  },
  "keyword_scraper": {
    "enabled": false
  },
  "keyword_api": {
    "real_api": {
      "enabled": false,
      "api_key": "your_real_keyword_api_key_here"
    },
    "metrics_api": {
      "enabled": false,
      "api_key": "your_keyword_metrics_api_key_here"
    }
  },
  "technical_auditor": {
    "lighthouse_path": "lighthouse"
  },
  "clickhouse": {
    "enabled": false,
    "host": "localhost",
    "port": 9000,
    "user": "default",
    "password": "",
    "database": "default"
  },
  "ai": {
    "openrouter_api_key": "your_openrouter_key_here",
    "cache_ttl": 3600,
    "enabled": false,
    "models": {
      "content_scoring": "anthropic/claude-3-haiku",
      "content_gap_analysis": "openai/gpt-4-turbo",
      "keyword_research": "google/gemini-pro",
      "technical_seo_analysis": "anthropic/claude-3-5-sonnet",
      "competitor_analysis": "openai/gpt-4",
      "content_generation": "anthropic/claude-3-5-sonnet"
    }
  },
  "api_cache": {
    "enabled": true,
    "ttl": 3600
  },
  "api_rate_limiter": {
    "enabled": true,
    "requests_per_second": 1.0,
    "max_retries": 3,
    "retry_backoff_factor": 0.5
  }
}"""
    
    with open("Link_Profiler/config/default.json", "w") as f:
        f.write(default_config)
    print("  ✅ Created Link_Profiler/config/default.json")
    
    # Environment template
    env_template = """# Redis Configuration
LP_REDIS_URL=redis://localhost:6379

# Database Configuration  
LP_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/link_profiler_db

# Queue System Configuration
LP_QUEUE_DEAD_LETTER_QUEUE_NAME=dead_letter_queue
LP_QUEUE_MAX_SATELLITES=10
LP_QUEUE_DEFAULT_QUEUE_PRIORITY=5
LP_QUEUE_HEARTBEAT_INTERVAL=30

# API Configuration
LP_API_HOST=0.0.0.0
LP_API_PORT=8000

# Monitoring Configuration
LP_MONITORING_MONITOR_PORT=8001
LP_LOGGING_LEVEL=INFO

# Docker Configuration
LP_COMPOSE_PROJECT_NAME=linkprofiler

# Environment
LP_ENVIRONMENT=development

# External API Keys (optional)
# LP_DOMAIN_API_ABSTRACT_API_ENABLED=false
# LP_DOMAIN_API_ABSTRACT_API_API_KEY=your_abstract_api_key_here

# LP_BACKLINK_API_OPENLINKPROFILER_API_ENABLED=false
# LP_BACKLINK_API_GSC_API_ENABLED=false
# LP_BACKLINK_API_REAL_API_ENABLED=false
# LP_BACKLINK_API_REAL_API_KEY=your_real_backlink_api_key_here

# LP_SERP_CRAWLER_PLAYWRIGHT_ENABLED=false
# LP_SERP_CRAWLER_PLAYWRIGHT_HEADLESS=true
# LP_SERP_CRAWLER_PLAYWRIGHT_BROWSER_TYPE=chromium
# LP_SERP_API_REAL_API_ENABLED=false
# LP_SERP_API_REAL_API_KEY=your_real_serp_api_key_here

# LP_KEYWORD_SCRAPER_ENABLED=false
# LP_KEYWORD_API_REAL_API_ENABLED=false
# LP_KEYWORD_API_REAL_API_KEY=your_real_keyword_api_key_here
# LP_KEYWORD_API_METRICS_API_ENABLED=false
# LP_KEYWORD_API_METRICS_API_KEY=your_keyword_metrics_api_key_here

# LP_TECHNICAL_AUDITOR_LIGHTHOUSE_PATH=lighthouse

# ClickHouse Integration (optional)
# LP_CLICKHOUSE_ENABLED=false
# LP_CLICKHOUSE_HOST=localhost
# LP_CLICKHOUSE_PORT=9000
# LP_CLICKHOUSE_USER=default
# LP_CLICKHOUSE_PASSWORD=
# LP_CLICKHOUSE_DATABASE=default

# Crawler Configuration
LP_CRAWLER_RESPECT_ROBOTS_TXT=true

# AI Integration (OpenRouter)
LP_AI_ENABLED=false
LP_AI_OPENROUTER_API_KEY=your_openrouter_key_here
LP_AI_CACHE_TTL=3600

# API Response Caching (for Domain/Backlink services)
LP_API_CACHE_ENABLED=true
LP_API_CACHE_TTL=3600

# API Rate Limiting (for external API calls)
LP_API_RATE_LIMITER_ENABLED=true
LP_API_RATE_LIMITER_REQUESTS_PER_SECOND=1.0
LP_API_RATE_LIMITER_MAX_RETRIES=3
LP_API_RATE_LIMITER_RETRY_BACKOFF_FACTOR=0.5
"""
    
    with open(".env.example", "w") as f:
        f.write(env_template)
    print("  ✅ Created .env.example")

def create_startup_scripts():
    """Create helpful startup scripts"""
    print("\n🚀 Creating startup scripts...")
    
    # Local development startup script (Linux/macOS)
    local_startup_sh = """#!/bin/bash
# Local Development Startup Script

echo "🚀 Starting Link Profiler Queue System (Local Development)"

# Check if Redis is running
if ! redis-cli ping > /dev/null 2>&1; then
    echo "❌ Redis is not running. Please start Redis first:"
    echo "   Ubuntu/Debian: sudo systemctl start redis"
    echo "   macOS: brew services start redis" 
    echo "   Docker: docker run -d -p 6379:6379 redis:7-alpine"
    exit 1
fi

echo "✅ Redis is running"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies
echo "📦 Installing dependencies..."
pip install -r requirements.txt

# Set PYTHONPATH to include the project root
export PYTHONPATH=$(pwd)

# Start components in background
echo "🚀 Starting coordinator..."
uvicorn Link_Profiler.main:app --host 0.0.0.0 --port 8000 --reload &
COORDINATOR_PID=$!

echo "🛰️ Starting satellite crawler..."
python -m Link_Profiler.queue_system.satellite_crawler --region local-dev &
SATELLITE_PID=$!

echo "📊 Starting monitoring dashboard..."
python -m Link_Profiler.monitoring.dashboard dashboard &
MONITOR_PID=$!

echo "✅ All components started!"
echo "🌐 API: http://localhost:8000"
echo "📊 Monitor: http://localhost:8001"
echo "📖 API Docs: http://localhost:8000/docs"

# Wait for interrupt
trap "kill $COORDINATOR_PID $SATELLITE_PID $MONITOR_PID" EXIT
wait
"""
    
    with open("scripts/start_local.sh", "w") as f:
        f.write(local_startup_sh)
    os.chmod("scripts/start_local.sh", 0o755)
    print("  ✅ Created scripts/start_local.sh")

    # Local development startup script (Windows)
    local_startup_bat = """@echo off
REM Windows version of local startup script

echo Starting Link Profiler Queue System (Local Development)

REM Check if Redis is running (requires Redis CLI in PATH)
redis-cli ping >nul 2>&1
if %errorlevel% neq 0 (
    echo Redis is not running. Please start Redis first:
    echo   Docker: docker run -d -p 6379:6379 redis:7-alpine
    echo   Or install Redis for Windows
    exit /b 1
)

echo Redis is running

REM Check if virtual environment exists
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
call venv\\Scripts\\activate.bat

REM Install dependencies
echo Installing dependencies...
pip install -r requirements.txt

REM Set PYTHONPATH to include the project root
set PYTHONPATH=%cd%

REM Start components
echo Starting coordinator (API server)...
start "Coordinator" uvicorn Link_Profiler.main:app --host 0.0.0.0 --port 8000 --reload

echo Starting satellite crawler...
start "Satellite" python -m Link_Profiler.queue_system.satellite_crawler --region local-dev

echo Starting monitoring dashboard...
start "Monitor" python -m Link_Profiler.monitoring.dashboard dashboard

echo All components started!
echo API: http://localhost:8000
echo Monitor: http://localhost:8001
echo API Docs: http://localhost:8000/docs

pause
"""
    with open("scripts/start_local.bat", "w") as f:
        f.write(local_startup_bat)
    print("  ✅ Created scripts/start_local.bat")
    
    # Test script (already exists, just ensure it's mentioned)
    print("  ℹ️  tests/test_queue.py should already exist from previous steps.")

def create_requirements_txt():
    """Create a basic requirements.txt if it doesn't exist."""
    requirements_content = """fastapi
uvicorn[standard]
aiohttp
beautifulsoup4
lxml
SQLAlchemy
psycopg2-binary
google-api-python-client
google-auth-oauthlib
clickhouse-driver
playwright
playwright-stealth
pytrends
prometheus_client
openai
croniter

# Queue System Dependencies
redis>=4.5.0
jinja2>=3.1.0

# Development Dependencies
python-dotenv>=0.19.0
"""
    if not Path("requirements.txt").exists():
        with open("requirements.txt", "w") as f:
            f.write(requirements_content)
        print("  ✅ Created requirements.txt with core dependencies.")
    else:
        print("  ℹ️  requirements.txt already exists. Please ensure it contains all necessary dependencies.")


def copy_artifact_files_instructions():
    """Provide instructions for copying artifact files."""
    print("\n📄 File Placement Guide:")
    print("Please ensure the following files are in their correct locations:")
    print()
    
    file_mappings = [
        ("Link_Profiler/core/models.py", "Link_Profiler/core/models.py"),
        ("Link_Profiler/crawlers/web_crawler.py", "Link_Profiler/crawlers/web_crawler.py"),
        ("Link_Profiler/crawlers/content_parser.py", "Link_Profiler/crawlers/content_parser.py"),
        ("Link_Profiler/crawlers/link_extractor.py", "Link_Profiler/crawlers/link_extractor.py"),
        ("Link_Profiler/crawlers/robots_parser.py", "Link_Profiler/crawlers/robots_parser.py"),
        ("Link_Profiler/crawlers/serp_crawler.py", "Link_Profiler/crawlers/serp_crawler.py"),
        ("Link_Profiler/crawlers/keyword_scraper.py", "Link_Profiler/crawlers/keyword_scraper.py"),
        ("Link_Profiler/crawlers/technical_auditor.py", "Link_Profiler/crawlers/technical_auditor.py"),
        ("Link_Profiler/services/crawl_service.py", "Link_Profiler/services/crawl_service.py"),
        ("Link_Profiler/services/domain_service.py", "Link_Profiler/services/domain_service.py"),
        ("Link_Profiler/services/backlink_service.py", "Link_Profiler/services/backlink_service.py"),
        ("Link_Profiler/services/domain_analyzer_service.py", "Link_Profiler/services/domain_analyzer_service.py"),
        ("Link_Profiler/services/expired_domain_finder_service.py", "Link_Profiler/services/expired_domain_finder_service.py"),
        ("Link_Profiler/services/serp_service.py", "Link_Profiler/services/serp_service.py"),
        ("Link_Profiler/services/keyword_service.py", "Link_Profiler/services/keyword_service.py"),
        ("Link_Profiler/services/link_health_service.py", "Link_Profiler/services/link_health_service.py"),
        ("Link_Profiler/services/ai_service.py", "Link_Profiler/services/ai_service.py"),
        ("Link_Profiler/database/database.py", "Link_Profiler/database/database.py"),
        ("Link_Profiler/database/models.py", "Link_Profiler/database/models.py"),
        ("Link_Profiler/database/clickhouse_loader.py", "Link_Profiler/database/clickhouse_loader.py"),
        ("Link_Profiler/api/main.py", "Link_Profiler/api/main.py"),
        ("Link_Profiler/api/queue_endpoints.py", "Link_Profiler/api/queue_endpoints.py"),
        ("Link_Profiler/monitoring/dashboard.py", "Link_Profiler/monitoring/dashboard.py"),
        ("Link_Profiler/monitoring/prometheus_metrics.py", "Link_Profiler/monitoring/prometheus_metrics.py"),
        ("admin-management-console/dashboard.html", "admin-management-console/dashboard.html"),
        ("Link_Profiler/queue_system/job_coordinator.py", "Link_Profiler/queue_system/job_coordinator.py"),
        ("Link_Profiler/queue_system/satellite_crawler.py", "Link_Profiler/queue_system/satellite_crawler.py"),
        ("Link_Profiler/config/config_loader.py", "Link_Profiler/config/config_loader.py"),
        ("Link_Profiler/config/default.json", "Link_Profiler/config/default.json"),
        ("Link_Profiler/config/development.json", "Link_Profiler/config/development.json"),
        ("Link_Profiler/config/production.json", "Link_Profiler/config/production.json"),
        ("Link_Profiler/utils/logging_config.py", "Link_Profiler/utils/logging_config.py"),
        ("Link_Profiler/utils/user_agent_manager.py", "Link_Profiler/utils/user_agent_manager.py"),
        ("Link_Profiler/utils/proxy_manager.py", "Link_Profiler/utils/proxy_manager.py"),
        ("Link_Profiler/utils/content_validator.py", "Link_Profiler/utils/content_validator.py"),
        ("Link_Profiler/utils/data_exporter.py", "Link_Profiler/utils/data_exporter.py"),
        ("tests/test_api.py", "tests/test_api.py"),
        ("setup.py", "setup.py"),
        (".env.example", ".env.example"),
        (".gitignore", ".gitignore"),
        ("deployment/docker/docker-compose.yml", "deployment/docker/docker-compose.yml"),
        ("deployment/docker/Dockerfile.coordinator", "deployment/docker/Dockerfile.coordinator"),
        ("deployment/docker/Dockerfile.monitor", "deployment/docker/Dockerfile.monitor"),
        ("deployment/docker/Dockerfile.satellite", "deployment/docker/Dockerfile.satellite"),
        ("deployment/docker/deploy.sh", "deployment/docker/deploy.sh"),
        ("deployment/docker/scale-satellites.sh", "deployment/docker/scale-satellites.sh"),
        ("deployment/kubernetes/k8s-namespace.yaml", "deployment/kubernetes/k8s-namespace.yaml"),
        ("deployment/kubernetes/k8s-configmap.yaml", "deployment/kubernetes/k8s-configmap.yaml"),
        ("deployment/kubernetes/k8s-redis.yaml", "deployment/kubernetes/k8s-redis.yaml"),
        ("deployment/kubernetes/k8s-coordinator.yaml", "deployment/kubernetes/k8s-coordinator.yaml"),
        ("deployment/kubernetes/k8s-satellites.yaml", "deployment/kubernetes/k8s-satellites.yaml"),
        ("deployment/kubernetes/k8s-hpa.yaml", "deployment/kubernetes/k8s-hpa.yaml"),
        ("deployment/kubernetes/k8s-deploy.sh", "deployment/kubernetes/k8s-deploy.sh")
    ]
    
    for source, dest in file_mappings:
        print(f"  📁 {source} → {dest}")
    
    print("\n💡 Pro tip: Copy the content from the provided files into these locations.")

def main():
    """Main setup function"""
    print("🔗 Link Profiler Queue System Setup")
    print("=" * 40)
    
    # Check if we're in the right directory
    if not Path("Link_Profiler").exists():
        print("❌ Error: Please run this script from your Link_Profiler root directory")
        print("   (The directory containing the Link_Profiler package)")
        sys.exit(1)
    
    create_directory_structure()
    create_requirements_txt() # Ensure main requirements.txt exists
    create_config_files()
    create_startup_scripts()
    copy_artifact_files_instructions() # Provide instructions for all files
    
    print("\n✅ Setup Complete!")
    print("\n📋 Next Steps:")
    print("1. Ensure all files are copied to their correct locations as per the 'File Placement Guide'.")
    print("2. Install Redis: sudo apt install redis-server (Ubuntu) or brew install redis (macOS) or use Docker.")
    print("3. Start Redis: `redis-server` (if not using Docker).")
    print("4. Install PostgreSQL and create the database as per README.md.")
    print("5. Install Python dependencies: `pip install -r requirements.txt`.")
    print("6. Test setup: `python tests/test_queue.py` (or `python tests/test_api.py` for full API tests).")
    print("7. Start development: `./scripts/start_local.sh` (Linux/macOS) or `scripts\\start_local.bat` (Windows).")
    print("\n🎉 Happy crawling with distributed queues!")

if __name__ == "__main__":
    main()
