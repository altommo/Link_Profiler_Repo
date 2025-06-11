#!/usr/bin/env python3
"""
Quick Password Reset Script for Link Profiler
This script will reset the monitor_user password to the expected value
"""

import sys
import os
import asyncio

# Add the project root to Python path
sys.path.insert(0, '/opt/Link_Profiler_Repo')

async def reset_monitor_password():
    """Reset the monitor_user password"""
    try:
        from Link_Profiler.services.auth_service import auth_service_instance
        from Link_Profiler.database.database import db
        
        print("🔄 Resetting monitor_user password...")
        
        # Get the user
        user = db.get_user_by_username('monitor_user')
        if not user:
            print("❌ User 'monitor_user' not found!")
            return False
            
        print(f"Found user: {user.username} ({user.email})")
        
        # Hash the correct password
        correct_password = "secure_monitor_password_123"
        new_hash = auth_service_instance.get_password_hash(correct_password)
        
        print(f"Generating new hash for password: {correct_password}")
        
        # Update the user's password
        user.hashed_password = new_hash
        updated_user = db.update_user(user)
        
        print("✅ Password updated successfully!")
        
        # Test the new password
        print("🧪 Testing new password...")
        authenticated = await auth_service_instance.authenticate_user('monitor_user', correct_password)
        
        if authenticated:
            print("✅ Password reset successful! Authentication works.")
            print(f"✅ User can now login with username: monitor_user")
            print(f"✅ User can now login with password: {correct_password}")
            return True
        else:
            print("❌ Password reset failed - authentication still not working")
            return False
            
    except Exception as e:
        print(f"❌ Error resetting password: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    print("🔐 Link Profiler Password Reset Tool")
    print("=" * 40)
    
    success = await reset_monitor_password()
    
    if success:
        print("\n🎉 SUCCESS!")
        print("The monitor_user password has been reset.")
        print("You can now try logging in to the dashboard.")
    else:
        print("\n💥 FAILED!")
        print("Password reset did not work. Check the logs above for errors.")

if __name__ == "__main__":
    asyncio.run(main())
