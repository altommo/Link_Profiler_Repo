#!/usr/bin/env python3
"""
Authentication Debug Script for Link Profiler
This script will help identify and fix authentication issues
Run this on your server to debug the authentication problem
"""

import sys
import os
import traceback
from datetime import datetime
import asyncio

# Add the project root to Python path
sys.path.insert(0, '/opt/Link_Profiler_Repo')

def test_database_connection():
    """Test basic database connectivity"""
    print("=== Testing Database Connection ===")
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
        traceback.print_exc()
        return False

def test_config_loading():
    """Test configuration loading"""
    print("\n=== Testing Configuration Loading ===")
    try:
        from Link_Profiler.config.config_loader import config_loader
        
        # Check auth configuration
        secret_key = config_loader.get("auth.secret_key")
        algorithm = config_loader.get("auth.algorithm")
        expire_minutes = config_loader.get("auth.access_token_expire_minutes")
        
        print(f"Auth Secret Key: {'SET' if secret_key and secret_key != 'PLACEHOLDER_MUST_SET_LP_AUTH_SECRET_KEY' else 'NOT SET'}")
        if secret_key:
            print(f"Secret Key Preview: {secret_key[:10]}...")
        print(f"Algorithm: {algorithm}")
        print(f"Token Expire Minutes: {expire_minutes}")
        
        # Check database URL
        db_url = config_loader.get("database.url")
        print(f"Database URL: {'SET' if db_url else 'NOT SET'}")
        if db_url:
            # Mask password in URL for display
            import re
            masked_url = re.sub(r'://([^:]+):([^@]+)@', r'://\1:***@', db_url)
            print(f"Database URL Preview: {masked_url}")
            
        return True
    except Exception as e:
        print(f"❌ Configuration loading error: {e}")
        traceback.print_exc()
        return False

def test_user_lookup():
    """Test user lookup in database"""
    print("\n=== Testing User Lookup ===")
    try:
        from Link_Profiler.database.database import db
        
        # Try to find the monitor user
        user = db.get_user_by_username('monitor_user')
        if user:
            print("✅ User 'monitor_user' found in database")
            print(f"User ID: {user.id}")
            print(f"Username: {user.username}")
            print(f"Email: {user.email}")
            print(f"Is Active: {user.is_active}")
            print(f"Is Admin: {user.is_admin}")
            print(f"Role: {user.role}")
            print(f"Has Password Hash: {'YES' if user.hashed_password else 'NO'}")
            if user.hashed_password:
                print(f"Password Hash Preview: {user.hashed_password[:20]}...")
            return user
        else:
            print("❌ User 'monitor_user' not found in database")
            
            # List all users to see what's available
            all_users = db.get_all_users()
            print(f"Found {len(all_users)} users in database:")
            for u in all_users:
                print(f"  - {u.username} ({u.email}) - Active: {u.is_active}")
            return None
    except Exception as e:
        print(f"❌ User lookup error: {e}")
        traceback.print_exc()
        return None

def test_auth_service():
    """Test auth service initialization"""
    print("\n=== Testing Auth Service ===")
    try:
        from Link_Profiler.services.auth_service import auth_service_instance
        
        # Check if auth service has valid secret key
        if hasattr(auth_service_instance, 'secret_key'):
            if auth_service_instance.secret_key and auth_service_instance.secret_key != "PLACEHOLDER_MUST_SET_LP_AUTH_SECRET_KEY":
                print("✅ Auth service has valid secret key")
                print(f"Secret Key Preview: {auth_service_instance.secret_key[:10]}...")
            else:
                print("❌ Auth service secret key is invalid or placeholder")
                return False
        else:
            print("❌ Auth service missing secret_key attribute")
            return False
            
        print(f"Algorithm: {auth_service_instance.algorithm}")
        print(f"Token Expire Minutes: {auth_service_instance.access_token_expire_minutes}")
        return True
    except Exception as e:
        print(f"❌ Auth service error: {e}")
        traceback.print_exc()
        return False

def test_password_verification():
    """Test password verification with the actual user"""
    print("\n=== Testing Password Verification ===")
    try:
        from Link_Profiler.services.auth_service import auth_service_instance
        from Link_Profiler.database.database import db
        
        # Get the user
        user = db.get_user_by_username('monitor_user')
        if not user:
            print("❌ Cannot test password verification - user not found")
            return False
            
        # Test password verification
        test_password = "secure_monitor_password_123"
        print(f"Testing password: {test_password}")
        print(f"Against hash: {user.hashed_password[:50]}...")
        
        is_valid = auth_service_instance.verify_password(test_password, user.hashed_password)
        print(f"Password verification result: {'✅ VALID' if is_valid else '❌ INVALID'}")
        
        # Try a few variations in case there's an issue
        if not is_valid:
            print("\nTrying password variations:")
            variations = [
                "secure_monitor_password_123",  # Original
                "admin",  # Simple admin
                "password123",  # Common password
                "monitor_password",  # Simplified
            ]
            
            for pwd in variations:
                result = auth_service_instance.verify_password(pwd, user.hashed_password)
                print(f"  '{pwd}': {'✅ VALID' if result else '❌ INVALID'}")
                if result:
                    print(f"  >>> CORRECT PASSWORD FOUND: '{pwd}'")
                    break
        
        return is_valid
    except Exception as e:
        print(f"❌ Password verification error: {e}")
        traceback.print_exc()
        return False

async def test_authentication_flow():
    """Test the complete authentication flow"""
    print("\n=== Testing Complete Authentication Flow ===")
    try:
        from Link_Profiler.services.auth_service import auth_service_instance
        
        # Test authentication
        username = "monitor_user"
        password = "secure_monitor_password_123"
        
        print(f"Attempting authentication with username: {username}")
        print(f"Attempting authentication with password: {password}")
        
        user = await auth_service_instance.authenticate_user(username, password)
        
        if user:
            print("✅ Authentication successful!")
            print(f"Authenticated user: {user.username}")
            
            # Test token creation
            token_data = {
                "sub": user.username,
                "role": user.role,
                "organization_id": user.organization_id
            }
            token = auth_service_instance.create_access_token(token_data)
            print(f"✅ Token created: {token[:50]}...")
            
            # Test token verification
            decoded = auth_service_instance.decode_access_token(token)
            if decoded:
                print("✅ Token verification successful")
                print(f"Decoded username: {decoded.username}")
                print(f"Decoded role: {decoded.role}")
            else:
                print("❌ Token verification failed")
                
            return True
        else:
            print("❌ Authentication failed")
            return False
    except Exception as e:
        print(f"❌ Authentication flow error: {e}")
        traceback.print_exc()
        return False

def create_test_user():
    """Create a test user with known password"""
    print("\n=== Creating Test User ===")
    try:
        from Link_Profiler.services.auth_service import auth_service_instance
        from Link_Profiler.database.database import db
        import uuid
        
        # Check if test user already exists
        existing = db.get_user_by_username('test_monitor')
        if existing:
            print("Test user 'test_monitor' already exists, deleting...")
            db.delete_user(existing.id)
        
        # Create new test user with known password
        test_password = "test123"
        hashed_password = auth_service_instance.get_password_hash(test_password)
        
        from Link_Profiler.core.models import User
        test_user = User(
            id=str(uuid.uuid4()),
            username="test_monitor",
            email="test@example.com",
            hashed_password=hashed_password,
            is_active=True,
            is_admin=True,
            role="admin",
            organization_id=None
        )
        
        created_user = db.create_user(test_user)
        print(f"✅ Test user created: {created_user.username}")
        print(f"Test password: {test_password}")
        
        # Test authentication with new user
        print("Testing authentication with new test user...")
        authenticated = await auth_service_instance.authenticate_user('test_monitor', test_password)
        if authenticated:
            print("✅ Test user authentication successful!")
        else:
            print("❌ Test user authentication failed!")
            
        return True
    except Exception as e:
        print(f"❌ Test user creation error: {e}")
        traceback.print_exc()
        return False

def fix_monitor_user_password():
    """Fix the monitor_user password"""
    print("\n=== Fixing Monitor User Password ===")
    try:
        from Link_Profiler.services.auth_service import auth_service_instance
        from Link_Profiler.database.database import db
        
        # Get the existing user
        user = db.get_user_by_username('monitor_user')
        if not user:
            print("❌ Cannot fix password - user not found")
            return False
            
        # Hash the correct password
        correct_password = "secure_monitor_password_123"
        new_hash = auth_service_instance.get_password_hash(correct_password)
        
        print(f"Creating new password hash for: {correct_password}")
        print(f"New hash: {new_hash[:50]}...")
        
        # Update the user's password
        user.hashed_password = new_hash
        updated_user = db.update_user(user)
        
        print("✅ Password updated successfully")
        
        # Test the new password
        print("Testing new password...")
        is_valid = auth_service_instance.verify_password(correct_password, updated_user.hashed_password)
        print(f"Password verification: {'✅ VALID' if is_valid else '❌ INVALID'}")
        
        return is_valid
    except Exception as e:
        print(f"❌ Password fix error: {e}")
        traceback.print_exc()
        return False

def check_database_schema():
    """Check if database schema matches expected ORM models"""
    print("\n=== Checking Database Schema ===")
    try:
        from Link_Profiler.database.database import db
        
        # Test a simple query to see if schema is correct
        with db.engine.connect() as conn:
            # Check if created_at vs created_date issue exists
            try:
                result = conn.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'crawl_jobs'")
                columns = [row[0] for row in result]
                print(f"crawl_jobs table columns: {columns}")
                
                if 'created_at' in columns:
                    print("✅ crawl_jobs has 'created_at' column")
                elif 'created_date' in columns:
                    print("⚠️  crawl_jobs has 'created_date' but ORM expects 'created_at'")
                else:
                    print("❌ crawl_jobs missing both 'created_at' and 'created_date'")
                    
            except Exception as e:
                print(f"Could not check crawl_jobs schema: {e}")
                
            # Check users table
            try:
                result = conn.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'users'")
                columns = [row[0] for row in result]
                print(f"users table columns: {columns}")
                
                required_columns = ['id', 'username', 'email', 'hashed_password', 'is_active', 'is_admin']
                missing = [col for col in required_columns if col not in columns]
                if missing:
                    print(f"❌ users table missing columns: {missing}")
                else:
                    print("✅ users table has all required columns")
                    
            except Exception as e:
                print(f"Could not check users schema: {e}")
                
        return True
    except Exception as e:
        print(f"❌ Schema check error: {e}")
        traceback.print_exc()
        return False

async def main():
    """Run all tests"""
    print("🔍 Link Profiler Authentication Debug Script")
    print("=" * 50)
    
    # Run tests in order
    tests = [
        ("Database Connection", test_database_connection),
        ("Configuration Loading", test_config_loading),
        ("Database Schema Check", check_database_schema),
        ("User Lookup", test_user_lookup),
        ("Auth Service", test_auth_service),
        ("Password Verification", test_password_verification),
        ("Authentication Flow", test_authentication_flow),
    ]
    
    results = {}
    for test_name, test_func in tests:
        print(f"\n{'='*20} {test_name} {'='*20}")
        try:
            if asyncio.iscoroutinefunction(test_func):
                result = await test_func()
            else:
                result = test_func()
            results[test_name] = result
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
            results[test_name] = False
    
    # Summary
    print("\n" + "=" * 50)
    print("🏁 SUMMARY")
    print("=" * 50)
    
    all_passed = True
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name}: {status}")
        if not result:
            all_passed = False
    
    if not all_passed:
        print("\n🔧 ATTEMPTING FIXES...")
        print("=" * 30)
        
        # Try to fix password issue
        if not results.get("Password Verification", False):
            await fix_monitor_user_password()
            
        # Try to create test user if main auth is broken
        if not results.get("Authentication Flow", False):
            await create_test_user()
    
    print(f"\n🎯 Overall Status: {'✅ ALL TESTS PASSED' if all_passed else '❌ SOME TESTS FAILED'}")

if __name__ == "__main__":
    asyncio.run(main())
