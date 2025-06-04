#!/usr/bin/env python3
"""
Admin User Management Script
Usage: python manage_admin.py <username> <action>
Actions: promote, demote, check
"""

import sys
import os

# Add the project root to path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from Link_Profiler.database.database import Database
from Link_Profiler.config.config_loader import ConfigLoader

def main():
    if len(sys.argv) != 3:
        print("Usage: python manage_admin.py <username> <action>")
        print("Actions: promote, demote, check")
        sys.exit(1)
    
    username = sys.argv[1]
    action = sys.argv[2].lower()
    
    # Hardcoded database credentials - correct ones from your setup
    DATABASE_URL = "postgresql://linkprofiler:secure_password_123@localhost:5432/link_profiler_db"
    
    # Initialize database
    db = Database(db_url=DATABASE_URL)
    
    try:
        # Get user from database
        user = db.get_user_by_username(username)
        
        if not user:
            print(f"Error: User '{username}' not found")
            sys.exit(1)
        
        if action == "check":
            status = "ADMIN" if user.is_admin else "REGULAR USER"
            print(f"User '{username}' is currently: {status}")
            
        elif action == "promote":
            if user.is_admin:
                print(f"User '{username}' is already an admin")
            else:
                # Update user to admin
                db.update_user_admin_status(username, True)
                print(f"User '{username}' has been promoted to admin")
                
        elif action == "demote":
            if not user.is_admin:
                print(f"User '{username}' is already a regular user")
            else:
                # Remove admin privileges
                db.update_user_admin_status(username, False)
                print(f"User '{username}' has been demoted to regular user")
                
        else:
            print(f"Error: Unknown action '{action}'")
            print("Valid actions: promote, demote, check")
            sys.exit(1)
            
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
    finally:
        if hasattr(db, 'Session'):
            db.Session.remove()

if __name__ == "__main__":
    main()
