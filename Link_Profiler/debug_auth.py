#!/usr/bin/env python3
"""
Authentication Debugging Script
Helps diagnose authentication issues in Link Profiler
"""

import os
import sys
import asyncio
import logging
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_config_loading():
    """Test configuration loading"""
    print("🔧 Testing Configuration Loading...")
    try:
        from Link_Profiler.config.config_loader import config_loader
        
        # Test key configuration values
        db_url = config_loader.get("database.url")
        redis_url = config_loader.get("redis.url") 
        auth_secret = config_loader.get("auth.secret_key")
        
        print(f"✅ Config loaded successfully")
        print(f"   Database URL: {'SET' if db_url else 'NOT SET'} ({db_url[:50] + '...' if db_url else 'None'})")
        print(f"   Redis URL: {'SET' if redis_url else 'NOT SET'} ({redis_url[:50] + '...' if redis_url else 'None'})")
        print(f"   Auth Secret: {'SET' if auth_secret and auth_secret != 'PLACEHOLDER_MUST_SET_LP_AUTH_SECRET_KEY' else 'NOT SET/PLACEHOLDER'}")
        
        return True
    except Exception as e:
        print(f"❌ Config loading failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_database_connection():
    """Test database connection"""
    print("\n🗄️  Testing Database Connection...")
    try:
        from Link_Profiler.database.database import db
        
        if db.ping():
            print("✅ Database connection successful")
            return True
        else:
            print("❌ Database ping failed")
            return False
    except Exception as e:
        print(f"❌ Database connection error: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_auth_service_initialization():
    """Test authentication service initialization"""
    print("\n🔐 Testing Auth Service Initialization...")
    try:
        from Link_Profiler.services.auth_service import auth_service_instance
        
        # Test if secret key is properly configured
        if hasattr(auth_service_instance, 'secret_key') and auth_service_instance.secret_key:
            if auth_service_instance.secret_key == "PLACEHOLDER_MUST_SET_LP_AUTH_SECRET_KEY":
                print("❌ Auth service using placeholder secret key")
                return False
            else:
                print("✅ Auth service initialized with valid secret key")
                print(f"   Secret key length: {len(auth_service_instance.secret_key)} characters")
                return True
        else:
            print("❌ Auth service secret key not set")
            return False
    except Exception as e:
        print(f"❌ Auth service initialization error: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_user_creation():
    """Test creating a test user"""
    print("\n👤 Testing User Creation...")
    try:
        from Link_Profiler.services.auth_service import auth_service_instance
        from Link_Profiler.database.database import db
        
        # Check if test user already exists
        existing_user = db.get_user_by_username("testuser")
        if existing_user:
            print("✅ Test user already exists")
            return True
        
        # Try to create a test user
        test_user = await auth_service_instance.register_user(
            username="testuser",
            email="test@example.com",
            password="testpassword123"
        )
        print("✅ Test user created successfully")
        return True
    except Exception as e:
        print(f"❌ User creation error: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_authentication():
    """Test user authentication"""
    print("\n🔑 Testing User Authentication...")
    try:
        from Link_Profiler.services.auth_service import auth_service_instance
        
        # Try to authenticate the test user
        user = await auth_service_instance.authenticate_user("testuser", "testpassword123")
        if user:
            print("✅ User authentication successful")
            print(f"   Username: {user.username}")
            print(f"   Email: {user.email}")
            print(f"   Is Admin: {user.is_admin}")
            print(f"   Is Active: {user.is_active}")
            return True
        else:
            print("❌ User authentication failed")
            return False
    except Exception as e:
        print(f"❌ Authentication error: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_token_creation():
    """Test JWT token creation and validation"""
    print("\n🎫 Testing JWT Token Creation and Validation...")
    try:
        from Link_Profiler.services.auth_service import auth_service_instance
        from datetime import timedelta
        
        # Create a test token
        token_data = {
            "sub": "testuser",
            "role": "customer",
            "organization_id": None
        }
        token = auth_service_instance.create_access_token(
            data=token_data,
            expires_delta=timedelta(minutes=30)
        )
        print("✅ JWT token created successfully")
        print(f"   Token length: {len(token)} characters")
        
        # Validate the token
        decoded_data = auth_service_instance.decode_access_token(token)
        if decoded_data:
            print("✅ JWT token validation successful")
            print(f"   Username: {decoded_data.username}")
            print(f"   Role: {decoded_data.role}")
            return True
        else:
            print("❌ JWT token validation failed")
            return False
    except Exception as e:
        print(f"❌ Token creation/validation error: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_api_endpoint():
    """Test the /token endpoint directly"""
    print("\n🌐 Testing /token Endpoint...")
    try:
        import httpx
        
        # Test the token endpoint
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "http://localhost:8000/token",
                data={
                    "username": "testuser",
                    "password": "testpassword123"
                },
                headers={
                    "Content-Type": "application/x-www-form-urlencoded"
                }
            )
            
            if response.status_code == 200:
                print("✅ /token endpoint successful")
                token_data = response.json()
                print(f"   Access token received: {len(token_data.get('access_token', ''))} characters")
                return True
            else:
                print(f"❌ /token endpoint failed: {response.status_code}")
                print(f"   Response: {response.text}")
                return False
    except Exception as e:
        print(f"❌ API endpoint test error: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Run all diagnostic tests"""
    print("🚀 Link Profiler Authentication Diagnostic Tool")
    print("=" * 50)
    
    tests = [
        ("Configuration Loading", test_config_loading),
        ("Database Connection", test_database_connection),
        ("Auth Service Initialization", test_auth_service_initialization),
        ("User Creation", test_user_creation),
        ("User Authentication", test_authentication),
        ("JWT Token Handling", test_token_creation),
        ("API Endpoint", test_api_endpoint),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = await test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} crashed: {e}")
            results.append((test_name, False))
    
    print("\n" + "=" * 50)
    print("📊 TEST RESULTS SUMMARY")
    print("=" * 50)
    
    passed = 0
    failed = 0
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status:10} {test_name}")
        if result:
            passed += 1
        else:
            failed += 1
    
    print(f"\nTotal: {passed} passed, {failed} failed")
    
    if failed > 0:
        print("\n🔍 RECOMMENDATIONS:")
        for test_name, result in results:
            if not result:
                if "Configuration" in test_name:
                    print("   - Check environment variables in systemd service file")
                    print("   - Verify config.yaml exists and is readable")
                elif "Database" in test_name:
                    print("   - Check if PostgreSQL is running: sudo systemctl status postgresql")
                    print("   - Verify database credentials and connection string")
                    print("   - Test manual connection: psql -h localhost -U linkprofiler -d link_profiler_db")
                elif "Auth Service" in test_name:
                    print("   - Check LP_AUTH_SECRET_KEY environment variable")
                    print("   - Ensure secret key is not the placeholder value")
                elif "User Creation" in test_name:
                    print("   - Database tables may not exist - check migrations")
                    print("   - Check database user permissions")
                elif "API Endpoint" in test_name:
                    print("   - Make sure the API server is running on port 8000")
                    print("   - Check if there are firewall or networking issues")

if __name__ == "__main__":
    asyncio.run(main())
