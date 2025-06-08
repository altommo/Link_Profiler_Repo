#!/usr/bin/env python3
"""
Fixed Authentication Diagnostic
Properly handles module imports and environment variables
"""

import sys
import os
from pathlib import Path

# Fix the Python path for Link_Profiler module
current_dir = Path(__file__).parent
project_root = current_dir.parent  # Go up one level to find Link_Profiler_Repo
link_profiler_path = project_root / "Link_Profiler"

# Add both paths to ensure module can be found
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(current_dir))

print(f"🔍 Project root: {project_root}")
print(f"🔍 Link_Profiler path: {link_profiler_path}")
print(f"🔍 Current working directory: {os.getcwd()}")
print(f"🔍 Python path: {sys.path[:3]}...")

def check_environment_variables():
    """Check if the required environment variables are set"""
    print("\n🔍 Checking Environment Variables...")
    
    required_vars = [
        'LP_DATABASE_URL',
        'LP_AUTH_SECRET_KEY', 
        'LP_REDIS_URL'
    ]
    
    missing_vars = []
    for var in required_vars:
        value = os.getenv(var)
        if value:
            # Mask sensitive information
            if 'password' in value.lower() or 'secret' in var.lower():
                masked_value = value[:10] + "***" + value[-4:] if len(value) > 14 else "***"
                print(f"✅ {var}: SET ({masked_value})")
            else:
                print(f"✅ {var}: SET ({value[:30]}...)")
        else:
            print(f"❌ {var}: NOT SET")
            missing_vars.append(var)
    
    return len(missing_vars) == 0

def check_systemd_env_vars():
    """Check what environment variables are set in systemd service"""
    print("\n🔧 Checking Systemd Service Environment...")
    
    service_file = "/etc/systemd/system/linkprofiler-api.service"
    if os.path.exists(service_file):
        try:
            with open(service_file, 'r') as f:
                content = f.read()
                
            env_lines = [line for line in content.split('\n') if line.strip().startswith('Environment=')]
            print(f"Found {len(env_lines)} environment variables in service file:")
            
            for line in env_lines:
                var_part = line.split('Environment=')[1]
                var_name = var_part.split('=')[0]
                if 'SECRET' in var_name or 'PASSWORD' in var_name:
                    print(f"   🔑 {var_name}=***")
                else:
                    print(f"   📝 {var_part[:50]}...")
                    
        except Exception as e:
            print(f"❌ Error reading service file: {e}")
    else:
        print(f"❌ Service file not found: {service_file}")

def test_direct_database_connection():
    """Test database connection using psycopg2 directly"""
    print("\n🗄️  Testing Direct Database Connection...")
    
    db_url = os.getenv('LP_DATABASE_URL')
    if not db_url:
        print("❌ LP_DATABASE_URL not set")
        return False
    
    try:
        import psycopg2
        from urllib.parse import urlparse
        
        # Parse the database URL
        parsed = urlparse(db_url)
        
        conn = psycopg2.connect(
            host=parsed.hostname,
            port=parsed.port or 5432,
            user=parsed.username,
            password=parsed.password,
            database=parsed.path[1:]  # Remove leading /
        )
        
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()[0]
        
        cursor.close()
        conn.close()
        
        print("✅ Direct database connection successful")
        print(f"   PostgreSQL version: {version[:50]}...")
        return True
        
    except Exception as e:
        print(f"❌ Direct database connection failed: {e}")
        return False

def test_redis_connection():
    """Test Redis connection directly"""
    print("\n🔴 Testing Redis Connection...")
    
    redis_url = os.getenv('LP_REDIS_URL')
    if not redis_url:
        print("❌ LP_REDIS_URL not set")
        return False
    
    try:
        import redis
        from urllib.parse import urlparse
        
        # Parse Redis URL
        parsed = urlparse(redis_url)
        
        r = redis.Redis(
            host=parsed.hostname or 'localhost',
            port=parsed.port or 6379,
            password=parsed.password,
            db=int(parsed.path[1:]) if parsed.path and len(parsed.path) > 1 else 0
        )
        
        # Test connection
        r.ping()
        info = r.info()
        
        print("✅ Redis connection successful")
        print(f"   Redis version: {info.get('redis_version', 'unknown')}")
        print(f"   Used memory: {info.get('used_memory_human', 'unknown')}")
        return True
        
    except Exception as e:
        print(f"❌ Redis connection failed: {e}")
        return False

def test_config_loader():
    """Test the configuration loader with fixed imports"""
    print("\n🔧 Testing Configuration Loader...")
    try:
        # Try different import paths
        try:
            from Link_Profiler.config.config_loader import config_loader
        except ImportError:
            try:
                from config.config_loader import config_loader
            except ImportError:
                sys.path.append('/opt/Link_Profiler_Repo')
                from Link_Profiler.config.config_loader import config_loader
        
        db_url = config_loader.get("database.url")
        auth_key = config_loader.get("auth.secret_key")
        redis_url = config_loader.get("redis.url")
        
        print(f"✅ Config loader imported successfully")
        print(f"   Database URL from config: {'SET' if db_url else 'NOT SET'}")
        print(f"   Auth secret from config: {'SET' if auth_key and auth_key != 'PLACEHOLDER_MUST_SET_LP_AUTH_SECRET_KEY' else 'NOT SET/PLACEHOLDER'}")
        print(f"   Redis URL from config: {'SET' if redis_url else 'NOT SET'}")
        
        return all([db_url, auth_key, redis_url]) and auth_key != 'PLACEHOLDER_MUST_SET_LP_AUTH_SECRET_KEY'
        
    except Exception as e:
        print(f"❌ Config loader error: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_required_services():
    """Check if required services are running"""
    print("\n🔄 Checking Required Services...")
    
    services = ['postgresql', 'redis-server', 'linkprofiler-api']
    
    for service in services:
        try:
            result = os.system(f"systemctl is-active {service} > /dev/null 2>&1")
            if result == 0:
                print(f"✅ {service}: RUNNING")
            else:
                print(f"❌ {service}: NOT RUNNING")
        except Exception as e:
            print(f"⚠️  {service}: UNKNOWN ({e})")

def suggest_fixes():
    """Provide specific fix suggestions based on findings"""
    print("\n🔧 SUGGESTED FIXES:")
    
    # Check if we're missing environment variables
    if not os.getenv('LP_AUTH_SECRET_KEY'):
        print("\n1. Missing LP_AUTH_SECRET_KEY:")
        print("   Add to systemd service file:")
        print("   Environment=LP_AUTH_SECRET_KEY=your-secure-secret-key-here")
        
    if not os.getenv('LP_REDIS_URL'):
        print("\n2. Missing LP_REDIS_URL:")
        print("   Add to systemd service file:")
        print("   Environment=LP_REDIS_URL=redis://localhost:6379/0")
        print("   or if Redis has password:")
        print("   Environment=LP_REDIS_URL=redis://:password@localhost:6379/0")
    
    print("\n3. After adding environment variables:")
    print("   sudo systemctl daemon-reload")
    print("   sudo systemctl restart linkprofiler-api")
    
    print("\n4. Test the fix:")
    print("   python quick_auth_check.py")

def main():
    """Run the diagnostic"""
    print("🚀 Link Profiler Authentication Quick Diagnostic (Fixed)")
    print("=" * 60)
    
    # Check environment variables
    env_ok = check_environment_variables()
    
    # Check systemd service configuration
    check_systemd_env_vars()
    
    # Check required services
    check_required_services()
    
    # Test direct connections
    db_ok = test_direct_database_connection()
    redis_ok = test_redis_connection()
    
    # Test configuration loader
    config_ok = test_config_loader()
    
    print("\n" + "=" * 60)
    print("📊 SUMMARY:")
    print(f"Environment variables: {'✅ PASS' if env_ok else '❌ FAIL'}")
    print(f"Database connection: {'✅ PASS' if db_ok else '❌ FAIL'}")
    print(f"Redis connection: {'✅ PASS' if redis_ok else '❌ FAIL'}")
    print(f"Config loader: {'✅ PASS' if config_ok else '❌ FAIL'}")
    
    if not (env_ok and db_ok and redis_ok):
        suggest_fixes()
    else:
        print("\n🎉 All basic checks passed! Authentication should work now.")

if __name__ == "__main__":
    main()
