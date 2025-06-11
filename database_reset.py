#!/usr/bin/env python3
"""
Quick Database Connection Reset Script
Run this to reset database connections and clear any stuck transactions
"""

import sys
import os
import asyncio
import logging

# Add the Link_Profiler directory to sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'Link_Profiler'))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def reset_database_connections():
    """Reset database connections and clear any stuck transactions"""
    print("🔄 Resetting database connections...")
    
    try:
        from Link_Profiler.database.database import db
        
        # Close all existing connections
        db.engine.dispose()
        print("   ✅ Database connection pool disposed")
        
        # Test new connection
        from sqlalchemy import text
        with db.get_session() as session:
            result = session.execute(text("SELECT 1")).fetchone()
            if result:
                print("   ✅ New database connection established successfully")
                return True
            else:
                print("   ❌ Database connection test failed")
                return False
                
    except Exception as e:
        print(f"   ❌ Database reset error: {e}")
        return False

def check_database_schema():
    """Check if required database columns exist"""
    print("\n🔍 Checking database schema...")
    
    try:
        from Link_Profiler.database.database import db
        
        # Check if required columns exist
        from sqlalchemy import text
        with db.get_session() as session:
            columns_check = session.execute(
                text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'crawl_jobs' 
                    AND column_name IN ('errors', 'created_at', 'config')
                """)
            ).fetchall()
            
            found_columns = [c[0] for c in columns_check]
            print(f"   Found columns: {found_columns}")
            
            if len(found_columns) >= 3:
                print("   ✅ All required columns exist")
                return True
            else:
                print(f"   ⚠️  Missing some columns. Found: {found_columns}")
                print("   Run the database migration script to add missing columns")
                return False
                
    except Exception as e:
        print(f"   ❌ Schema check error: {e}")
        return False

def main():
    """Main function to reset database and check status"""
    print("🚀 Database Reset & Check Script")
    print("=" * 40)
    
    success_count = 0
    total_tests = 2
    
    # Test 1: Reset database connections
    if reset_database_connections():
        success_count += 1
    
    # Test 2: Check database schema
    if check_database_schema():
        success_count += 1
    
    print("\n" + "=" * 40)
    print(f"📊 RESULTS: {success_count}/{total_tests} checks passed")
    
    if success_count == total_tests:
        print("\n🎉 Database is ready! You can restart the service:")
        print("   sudo systemctl restart linkprofiler-api.service")
        return True
    else:
        print("\n⚠️  Some issues found. Fix them before restarting the service.")
        if success_count == 0:
            print("\n💡 Try running the database migration first:")
            print("   sudo -u postgres psql -d link_profiler_db -f database_schema_migration.sql")
        return False

if __name__ == "__main__":
    try:
        result = main()
        sys.exit(0 if result else 1)
    except Exception as e:
        print(f"\n💥 Critical error: {e}")
        sys.exit(1)
