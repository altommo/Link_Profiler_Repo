#!/usr/bin/env python3
"""
User Management Script
Creates test users and verifies authentication flow
"""

import sys
import asyncio
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

async def create_test_user():
    """Create a test user for authentication testing"""
    print("👤 Creating Test User...")
    try:
        from Link_Profiler.services.auth_service import auth_service_instance
        from Link_Profiler.database.database import db
        
        # Check if test user already exists
        existing_user = db.get_user_by_username("admin")
        if existing_user:
            print("✅ Admin user already exists")
            return existing_user
        
        # Create admin user
        admin_user = await auth_service_instance.register_user(
            username="admin",
            email="admin@linkprofiler.com",
            password="admin123",
            is_admin=True,
            role="admin"
        )
        print("✅ Admin user created successfully")
        print(f"   Username: admin")
        print(f"   Password: admin123")
        print(f"   Role: admin")
        return admin_user
        
    except Exception as e:
        print(f"❌ Failed to create admin user: {e}")
        return None

async def test_authentication_flow():
    """Test the complete authentication flow"""
    print("\n🔑 Testing Authentication Flow...")
    try:
        from Link_Profiler.services.auth_service import auth_service_instance
        
        # Test authentication
        user = await auth_service_instance.authenticate_user("admin", "admin123")
        if not user:
            print("❌ Authentication failed")
            return False
        
        print("✅ Authentication successful")
        
        # Test token creation
        from datetime import timedelta
        token_data = {
            "sub": user.username,
            "role": user.role,
            "organization_id": user.organization_id
        }
        
        token = auth_service_instance.create_access_token(
            data=token_data,
            expires_delta=timedelta(minutes=30)
        )
        
        print("✅ JWT token created")
        
        # Test token validation
        decoded_data = auth_service_instance.decode_access_token(token)
        if decoded_data and decoded_data.username == "admin":
            print("✅ JWT token validation successful")
            print(f"   Token contains: {decoded_data.username}, {decoded_data.role}")
            return True
        else:
            print("❌ JWT token validation failed")
            return False
            
    except Exception as e:
        print(f"❌ Authentication flow error: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_api_login():
    """Test login via API endpoint"""
    print("\n🌐 Testing API Login...")
    try:
        import httpx
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "http://localhost:8000/token",
                data={
                    "username": "admin",
                    "password": "admin123"
                },
                headers={
                    "Content-Type": "application/x-www-form-urlencoded"
                }
            )
            
            print(f"Response status: {response.status_code}")
            
            if response.status_code == 200:
                token_data = response.json()
                print("✅ API login successful")
                print(f"   Access token received: {len(token_data.get('access_token', ''))} chars")
                
                # Test using the token
                headers = {"Authorization": f"Bearer {token_data['access_token']}"}
                me_response = await client.get("http://localhost:8000/users/me", headers=headers)
                
                if me_response.status_code == 200:
                    user_data = me_response.json()
                    print("✅ Token validation via /users/me successful")
                    print(f"   User: {user_data.get('username')} ({user_data.get('role')})")
                    return True
                else:
                    print(f"❌ Token validation failed: {me_response.status_code}")
                    print(f"   Response: {me_response.text}")
                    return False
            else:
                print(f"❌ API login failed: {response.status_code}")
                print(f"   Response: {response.text}")
                return False
                
    except Exception as e:
        print(f"❌ API login test error: {e}")
        print("   Make sure the API server is running on localhost:8000")
        return False

async def show_all_users():
    """Display all users in the database"""
    print("\n👥 Current Users in Database:")
    try:
        from Link_Profiler.database.database import db
        
        users = db.get_all_users()
        if users:
            for user in users:
                print(f"   • {user.username} ({user.email}) - Role: {user.role}, Admin: {user.is_admin}")
        else:
            print("   No users found in database")
        
        return len(users)
    except Exception as e:
        print(f"❌ Error retrieving users: {e}")
        return 0

async def main():
    """Main function"""
    print("🚀 Link Profiler User Management & Auth Test")
    print("=" * 50)
    
    # Show current users
    user_count = await show_all_users()
    
    # Create test user if needed
    if user_count == 0:
        print("\n📝 No users found. Creating admin user...")
        await create_test_user()
    
    # Test authentication flow
    auth_success = await test_authentication_flow()
    
    # Test API endpoint
    api_success = await test_api_login()
    
    print("\n" + "=" * 50)
    print("📊 SUMMARY")
    print(f"Users in database: {user_count}")
    print(f"Authentication flow: {'✅ PASS' if auth_success else '❌ FAIL'}")
    print(f"API login test: {'✅ PASS' if api_success else '❌ FAIL'}")
    
    if auth_success and api_success:
        print("\n🎉 SUCCESS! Authentication is working correctly.")
        print("You can now log in to the dashboard with:")
        print("   Username: admin")
        print("   Password: admin123")
    else:
        print("\n⚠️  Some tests failed. Check the output above for details.")
        if not auth_success:
            print("   - Authentication service may not be properly configured")
        if not api_success:
            print("   - API server may not be running or accessible")

if __name__ == "__main__":
    asyncio.run(main())
