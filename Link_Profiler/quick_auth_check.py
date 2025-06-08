#!/usr/bin/env python3
"""
Quick Authentication Diagnostic
Focuses on the specific authentication failure issue
"""

import sys
import os
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def check_environment_variables():
    """Check if the required environment variables are set"""
    print("🔍 Checking Environment Variables...")
    
    required_vars = [
        'LP_DATABASE_URL',
        'LP_AUTH_SECRET_KEY', 
        'LP_REDIS_URL'
    ]
    
    missing_vars = []
    for var in required_vars:
        value = os.getenv(var)
        if value:
            print(f"✅ {var}: SET ({value[:30]}...)")
        else:
            print(f"❌ {var}: NOT SET")
            missing_vars.append(var)
    
    return len(missing_vars) == 0

def test_config_loader():
    """Test the configuration loader"""
    print("\n🔧 Testing Configuration Loader...")
    try:
        from Link_Profiler.config.config_loader import config_loader
        
        db_url = config_loader.get("database.url")
        auth_key = config_loader.get("auth.secret_key")
        redis_url = config_loader.get("redis.url")
        
        print(f"Database URL from config: {'SET' if db_url else 'NOT SET'}")
        print(f"Auth secret from config: {'SET' if auth_key and auth_key != 'PLACEHOLDER_MUST_SET_LP_AUTH_SECRET_KEY' else 'NOT SET/PLACEHOLDER'}")
        print(f"Redis URL from config: {'SET' if redis_url else 'NOT SET'}")
        
        return all([db_url, auth_key, redis_url]) and auth_key != 'PLACEHOLDER_MUST_SET_LP_AUTH_SECRET_KEY'
        
    except Exception as e:
        print(f"❌ Config loader error: {e}")
        return False

def test_database_ping():
    """Test database connectivity"""
    print("\n🗄️  Testing Database Connection...")
    try:
        from Link_Profiler.database.database import db
        
        if db.ping():
            print("✅ Database connection successful")
            return True
        else:
            print("❌ Database ping failed - check credentials/network")
            return False
    except Exception as e:
        print(f"❌ Database connection error: {e}")
        print("   Possible causes:")
        print("   - PostgreSQL service not running")
        print("   - Wrong credentials in environment variables")
        print("   - Network connectivity issues")
        print("   - Database doesn't exist")
        return False

def test_auth_service():
    """Test authentication service initialization"""
    print("\n🔐 Testing Authentication Service...")
    try:
        from Link_Profiler.services.auth_service import auth_service_instance
        
        # Check if the secret key is properly set
        if hasattr(auth_service_instance, 'secret_key'):
            if auth_service_instance.secret_key is None:
                print("❌ Auth service secret key is None")
                return False
            elif auth_service_instance.secret_key == 'PLACEHOLDER_MUST_SET_LP_AUTH_SECRET_KEY':
                print("❌ Auth service using placeholder secret key")
                return False
            else:
                print("✅ Auth service initialized with valid secret key")
                return True
        else:
            print("❌ Auth service missing secret_key attribute")
            return False
            
    except Exception as e:
        print(f"❌ Auth service error: {e}")
        return False

def test_user_table():
    """Test if user table exists and is accessible"""
    print("\n👥 Testing User Table Access...")
    try:
        from Link_Profiler.database.database import db
        
        # Try to get all users (should work even if empty)
        users = db.get_all_users()
        print(f"✅ User table accessible, found {len(users)} users")
        return True
    except Exception as e:
        print(f"❌ User table access error: {e}")
        print("   Possible causes:")
        print("   - User table doesn't exist (migrations not run)")
        print("   - Database user lacks permissions")
        print("   - Database schema mismatch")
        return False

def test_token_endpoint():
    """Test the specific /token endpoint that's failing"""
    print("\n🎫 Testing /token Endpoint Response...")
    try:
        # Import the FastAPI app
        from fastapi.testclient import TestClient
        from Link_Profiler.main import app
        
        client = TestClient(app)
        
        # Test with invalid credentials to see what error we get
        response = client.post(
            "/token",
            data={
                "username": "nonexistent",
                "password": "wrongpassword"
            }
        )
        
        print(f"Response status: {response.status_code}")
        print(f"Response body: {response.text}")
        
        if response.status_code == 500:
            print("❌ 500 error indicates server-side configuration issue")
            return False
        elif response.status_code == 401:
            print("✅ 401 error indicates auth service is working (just wrong credentials)")
            return True
        else:
            print(f"⚠️  Unexpected status code: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Token endpoint test error: {e}")
        return False

def main():
    """Run focused diagnostic tests"""
    print("🚀 Link Profiler Authentication Quick Diagnostic")
    print("=" * 55)
    
    tests = [
        check_environment_variables,
        test_config_loader,
        test_database_ping,
        test_auth_service,
        test_user_table,
        test_token_endpoint
    ]
    
    passed = 0
    for test in tests:
        if test():
            passed += 1
        print()  # Add spacing between tests
    
    print("=" * 55)
    print(f"📊 RESULT: {passed}/{len(tests)} tests passed")
    
    if passed < len(tests):
        print("\n🔧 NEXT STEPS:")
        if passed == 0:
            print("1. Check that PostgreSQL and Redis are running")
            print("2. Verify systemd service environment variables are correct")
            print("3. Test database connection manually")
        elif passed <= 2:
            print("1. Run database migrations: alembic upgrade head")
            print("2. Check database user permissions")
            print("3. Verify auth secret key is properly set")
        else:
            print("1. Check application logs for detailed error messages")
            print("2. Try creating a test user via database directly")
            print("3. Monitor systemd service status: systemctl status linkprofiler-api")

if __name__ == "__main__":
    main()
