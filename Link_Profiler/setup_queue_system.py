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
        "queue_system",
        "deployment/docker", 
        "deployment/kubernetes",
        "monitoring/templates",
        "scripts",
        "config"
    ]
    
    print("📁 Creating directory structure...")
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
        print(f"  ✅ Created: {directory}")
    
    # Create __init__.py files
    init_files = [
        "queue_system/__init__.py",
        "monitoring/__init__.py"
    ]
    
    for init_file in init_files:
        Path(init_file).touch()
        print(f"  ✅ Created: {init_file}")

def create_requirements_files():
    """Create requirements files"""
    print("\n📦 Creating requirements files...")
    
    # Update main requirements.txt
    main_requirements = [
        "redis>=4.5.0",
        "aioredis>=2.0.0", 
        "jinja2>=3.1.0"
    ]
    
    if Path("requirements.txt").exists():
        with open("requirements.txt", "r") as f:
            existing = f.read()
        
        with open("requirements.txt", "a") as f:
            f.write("\n# Queue System Dependencies\n")
            for req in main_requirements:
                if req.split(">=")[0] not in existing:
                    f.write(f"{req}\n")
        print("  ✅ Updated requirements.txt")
    else:
        print("  ⚠️  requirements.txt not found - you'll need to create it manually")
    
    # Create satellite requirements
    satellite_requirements = """redis>=4.5.0
aiohttp>=3.8.0
beautifulsoup4>=4.11.0
lxml>=4.9.0
"""
    
    with open("requirements-satellite.txt", "w") as f:
        f.write(satellite_requirements)
    print("  ✅ Created requirements-satellite.txt")

def create_config_files():
    """Create configuration files"""
    print("\n⚙️ Creating configuration files...")
    
    # Default config
    default_config = """{
  "crawler": {
    "max_depth": 3,
    "max_pages": 1000,
    "delay_seconds": 1.0,
    "timeout_seconds": 30,
    "respect_robots_txt": true,
    "follow_redirects": true,
    "extract_images": true,
    "extract_pdfs": false,
    "max_file_size_mb": 10
  },
  "queue": {
    "max_retries": 3,
    "retry_delay": 5,
    "priority_levels": [1, 5, 10],
    "heartbeat_interval": 30,
    "stale_timeout": 60
  },
  "monitoring": {
    "dashboard_refresh": 30,
    "max_job_history": 100,
    "performance_window": 3600
  }
}"""
    
    with open("config/default.json", "w") as f:
        f.write(default_config)
    print("  ✅ Created config/default.json")
    
    # Environment template
    env_template = """# Redis Configuration
REDIS_URL=redis://localhost:6379

# Database Configuration  
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/link_profiler_db

# Queue System Configuration
MAX_SATELLITES=10
DEFAULT_QUEUE_PRIORITY=5
HEARTBEAT_INTERVAL=30

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000

# Monitoring Configuration
MONITOR_PORT=8001
LOG_LEVEL=INFO

# Docker Configuration
COMPOSE_PROJECT_NAME=linkprofiler
"""
    
    with open(".env.example", "w") as f:
        f.write(env_template)
    print("  ✅ Created .env.example")

def create_startup_scripts():
    """Create helpful startup scripts"""
    print("\n🚀 Creating startup scripts...")
    
    # Local development startup script
    local_startup = """#!/bin/bash
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

# Start components in background
echo "🚀 Starting coordinator..."
python -m queue_system.job_coordinator &
COORDINATOR_PID=$!

echo "🛰️ Starting satellite crawler..."
python -m queue_system.satellite_crawler --region local-dev &
SATELLITE_PID=$!

echo "📊 Starting monitoring dashboard..."
python -m monitoring.dashboard &
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
        f.write(local_startup)
    os.chmod("scripts/start_local.sh", 0o755)
    print("  ✅ Created scripts/start_local.sh")
    
    # Test script
    test_script = """#!/usr/bin/env python3
'''
Test script for queue system functionality
'''
import asyncio
import json
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

async def test_queue_system():
    try:
        from queue_system.job_coordinator import JobCoordinator
        print("✅ JobCoordinator import successful")
        
        # Test Redis connection
        async with JobCoordinator() as coordinator:
            stats = await coordinator.get_queue_stats()
            print(f"✅ Redis connection successful: {stats}")
            
        print("✅ All tests passed!")
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_queue_system())
    sys.exit(0 if success else 1)
"""
    
    with open("scripts/test_queue.py", "w") as f:
        f.write(test_script)
    os.chmod("scripts/test_queue.py", 0o755)
    print("  ✅ Created scripts/test_queue.py")

def copy_artifact_files():
    """Guide user to copy the artifact files"""
    print("\n📄 File Placement Guide:")
    print("Now copy the artifact files to these locations:")
    print()
    
    file_mappings = [
        ("job_coordinator.py", "queue_system/job_coordinator.py"),
        ("satellite_crawler.py", "queue_system/satellite_crawler.py"), 
        ("monitoring.py", "monitoring/dashboard.py"),
        ("docker-compose.yml + Dockerfiles", "deployment/docker/"),
        ("k8s-*.yaml files", "deployment/kubernetes/"),
        ("dashboard.html", "monitoring/templates/dashboard.html")
    ]
    
    for source, dest in file_mappings:
        print(f"  📁 {source} → {dest}")
    
    print("\n💡 Pro tip: Copy the content from the artifacts above into these files")

def create_readme_update():
    """Create README update with queue system documentation"""
    readme_addition = """

## 🚀 Queue System Setup (New Feature)

### Quick Start
```bash
# 1. Setup directory structure
python setup_queue_system.py

# 2. Copy artifact files to appropriate locations (see output above)

# 3. Start local development
chmod +x scripts/start_local.sh
./scripts/start_local.sh

# 4. Test the system
python scripts/test_queue.py
```

### Production Deployment
```bash
# Docker Compose
cd deployment/docker
chmod +x deploy.sh
./deploy.sh

# Kubernetes
cd deployment/kubernetes  
chmod +x k8s-deploy.sh
./k8s-deploy.sh
```

### Queue API Endpoints
- `POST /queue/submit_crawl` - Submit crawl job to queue
- `GET /queue/job_status/{job_id}` - Get job status
- `GET /queue/stats` - Get queue statistics
- `GET /queue/manage/crawler_health` - Get satellite health

### Monitoring
- Dashboard: http://localhost:8001
- Queue Stats: http://localhost:8000/queue/stats
"""
    
    print("\n📚 README Update:")
    print("Add this section to your README.md:")
    print("=" * 50)
    print(readme_addition)

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
    create_requirements_files()
    create_config_files()
    create_startup_scripts()
    copy_artifact_files()
    create_readme_update()
    
    print("\n✅ Setup Complete!")
    print("\n📋 Next Steps:")
    print("1. Copy the artifact files as shown above")
    print("2. Install Redis: sudo apt install redis-server (Ubuntu) or brew install redis (macOS)")
    print("3. Start Redis: redis-server")
    print("4. Test setup: python scripts/test_queue.py")
    print("5. Start development: ./scripts/start_local.sh")
    print("\n🎉 Happy crawling with distributed queues!")

if __name__ == "__main__":
    main()
