#!/usr/bin/env python3
"""
Complete System Verification Script
Checks all components and dependencies for the Link Profiler Queue System
"""
import os
import sys
import importlib
import subprocess
from pathlib import Path

def check_file_exists(path, description):
    """Check if a file exists"""
    if Path(path).exists():
        print(f"✅ {description}: {path}")
        return True
    else:
        print(f"❌ {description}: {path} - NOT FOUND")
        return False

def check_directory_exists(path, description):
    """Check if a directory exists"""
    if Path(path).is_dir():
        print(f"✅ {description}: {path}")
        return True
    else:
        print(f"❌ {description}: {path} - NOT FOUND")
        return False

def check_import(module_name, description):
    """Check if a Python module can be imported"""
    try:
        importlib.import_module(module_name)
        print(f"✅ {description}: {module_name}")
        return True
    except ImportError as e:
        print(f"❌ {description}: {module_name} - {e}")
        return False

def check_redis_connection():
    """Check Redis connection"""
    try:
        import redis
        r = redis.Redis(host='localhost', port=6379, decode_responses=True)
        r.ping()
        print("✅ Redis connection: localhost:6379")
        return True
    except Exception as e:
        print(f"❌ Redis connection: {e}")
        return False

def main():
    """Main verification function"""
    print("🔗 Link Profiler Queue System Verification")
    print("=" * 50)
    
    # Get project root
    project_root = Path(__file__).parent
    print(f"📁 Project root: {project_root}")
    print()
    
    # Track overall status
    all_checks = []
    
    print("📦 Core Components")
    print("-" * 20)
    all_checks.append(check_file_exists(project_root / "Link_Profiler/queue_system/job_coordinator.py", "Job Coordinator"))
    all_checks.append(check_file_exists(project_root / "Link_Profiler/queue_system/satellite_crawler.py", "Satellite Crawler"))
    all_checks.append(check_file_exists(project_root / "Link_Profiler/queue_system/__init__.py", "Queue System Package"))
    all_checks.append(check_file_exists(project_root / "Link_Profiler/api/queue_endpoints.py", "Queue API Endpoints"))
    all_checks.append(check_file_exists(project_root / "Link_Profiler/api/main_with_queue.py", "Enhanced API"))
    print()
    
    print("🐳 Deployment Files")
    print("-" * 20)
    all_checks.append(check_file_exists(project_root / "Link_Profiler/deployment/docker/docker-compose.yml", "Docker Compose"))
    all_checks.append(check_file_exists(project_root / "Link_Profiler/deployment/docker/Dockerfile.coordinator", "Coordinator Dockerfile"))
    all_checks.append(check_file_exists(project_root / "Link_Profiler/deployment/docker/Dockerfile.satellite", "Satellite Dockerfile"))
    all_checks.append(check_file_exists(project_root / "Link_Profiler/deployment/docker/deploy.sh", "Deploy Script"))
    all_checks.append(check_file_exists(project_root / "Link_Profiler/deployment/kubernetes/k8s-namespace.yaml", "K8s Namespace"))
    all_checks.append(check_file_exists(project_root / "Link_Profiler/deployment/kubernetes/k8s-coordinator.yaml", "K8s Coordinator"))
    print()
    
    print("📊 Monitoring Components")
    print("-" * 20)
    all_checks.append(check_file_exists(project_root / "Link_Profiler/monitoring/dashboard.py", "Monitoring Dashboard"))
    all_checks.append(check_file_exists(project_root / "Link_Profiler/templates/dashboard.html", "Dashboard Template"))
    all_checks.append(check_file_exists(project_root / "Link_Profiler/monitoring/__init__.py", "Monitoring Package"))
    print()
    
    print("⚙️ Configuration Files")
    print("-" * 20)
    all_checks.append(check_file_exists(project_root / "Link_Profiler/config/default.json", "Default Config"))
    all_checks.append(check_file_exists(project_root / "Link_Profiler/config/production.json", "Production Config"))
    all_checks.append(check_file_exists(project_root / "Link_Profiler/.env.example", "Environment Template"))
    all_checks.append(check_file_exists(project_root / "requirements-satellite.txt", "Satellite Requirements"))
    print()
    
    print("🚀 Entry Points")
    print("-" * 20)
    all_checks.append(check_file_exists(project_root / "run_coordinator.py", "Coordinator Entry Point"))
    all_checks.append(check_file_exists(project_root / "run_satellite.py", "Satellite Entry Point"))
    all_checks.append(check_file_exists(project_root / "Link_Profiler/scripts/start_local.sh", "Local Start Script (Linux)"))
    all_checks.append(check_file_exists(project_root / "Link_Profiler/scripts/start_local.bat", "Local Start Script (Windows)"))
    all_checks.append(check_file_exists(project_root / "Link_Profiler/scripts/test_queue.py", "Test Script"))
    print()
    
    print("📚 Documentation")
    print("-" * 20)
    all_checks.append(check_file_exists(project_root / "QUEUE_SYSTEM.md", "Queue System Documentation"))
    print()
    
    print("🐍 Python Dependencies")
    print("-" * 20)
    all_checks.append(check_import("redis", "Redis Client"))
    all_checks.append(check_import("fastapi", "FastAPI"))
    all_checks.append(check_import("aiohttp", "Async HTTP Client"))
    all_checks.append(check_import("jinja2", "Jinja2 Templates"))
    print()
    
    print("🔗 Service Connectivity")
    print("-" * 20)
    redis_ok = check_redis_connection()
    all_checks.append(redis_ok)
    print()
    
    # Import tests
    print("📥 Import Tests")
    print("-" * 20)
    
    # Add project to path for testing
    sys.path.insert(0, str(project_root / "Link_Profiler"))
    
    try:
        from queue_system.job_coordinator import JobCoordinator
        print("✅ JobCoordinator import successful")
        all_checks.append(True)
    except Exception as e:
        print(f"❌ JobCoordinator import failed: {e}")
        all_checks.append(False)
    
    try:
        from queue_system.satellite_crawler import SatelliteCrawler
        print("✅ SatelliteCrawler import successful")
        all_checks.append(True)
    except Exception as e:
        print(f"❌ SatelliteCrawler import failed: {e}")
        all_checks.append(False)
    
    try:
        from api.queue_endpoints import add_queue_endpoints
        print("✅ Queue endpoints import successful")
        all_checks.append(True)
    except Exception as e:
        print(f"❌ Queue endpoints import failed: {e}")
        all_checks.append(False)
    
    print()
    
    # Final summary
    passed = sum(all_checks)
    total = len(all_checks)
    percentage = (passed / total) * 100
    
    print("📋 VERIFICATION SUMMARY")
    print("=" * 30)
    print(f"✅ Passed: {passed}/{total} ({percentage:.1f}%)")
    
    if percentage == 100:
        print("🎉 ALL CHECKS PASSED! System is ready for deployment.")
        print("\n🚀 Quick Start Commands:")
        print("   python run_coordinator.py")
        print("   python run_satellite.py --region local")
        print("   python -m Link_Profiler.api.main_with_queue")
    elif percentage >= 90:
        print("⚠️  Minor issues detected. System should work but may need attention.")
    elif percentage >= 70:
        print("🔧 Several issues detected. Review failed checks before deployment.")
    else:
        print("❌ Major issues detected. System needs significant attention.")
    
    if not redis_ok:
        print("\n💡 To fix Redis connection:")
        print("   Ubuntu/Debian: sudo apt install redis-server && sudo systemctl start redis")
        print("   macOS: brew install redis && brew services start redis")
        print("   Docker: docker run -d -p 6379:6379 redis:7-alpine")
    
    print(f"\n📖 Full documentation: {project_root}/QUEUE_SYSTEM.md")
    
    return percentage == 100

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
