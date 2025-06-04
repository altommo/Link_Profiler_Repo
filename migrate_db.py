#!/usr/bin/env python3
"""
Database migration script to add missing columns to crawl_jobs table
"""

import psycopg2
from psycopg2.sql import SQL, Identifier

def main():
    # Database connection parameters
    DB_HOST = "localhost"
    DB_PORT = "5432"
    DB_NAME = "link_profiler_db"
    DB_USER = "linkprofiler"
    DB_PASSWORD = "secure_password_123"

    try:
        # Connect to the database
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        cursor = conn.cursor()

        print("Connected to database successfully")

        # List of columns to add (excluding anomalies_detected which already exists)
        columns_to_add = [
            ("scheduled_at", "TIMESTAMP"),
            ("cron_schedule", "VARCHAR"),
            ("duration_seconds", "FLOAT")
        ]

        for column_name, column_def in columns_to_add:
            try:
                # Check if column exists
                cursor.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name='crawl_jobs' AND column_name=%s
                """, (column_name,))
                
                if cursor.fetchone():
                    print(f"Column '{column_name}' already exists, skipping")
                    continue

                # Add the column
                alter_sql = f"ALTER TABLE crawl_jobs ADD COLUMN {column_name} {column_def}"
                print(f"Adding column: {alter_sql}")
                cursor.execute(alter_sql)
                conn.commit()
                print(f"Successfully added column '{column_name}'")

            except Exception as e:
                print(f"Error adding column '{column_name}': {e}")
                conn.rollback()

        print("Migration completed")
        
        # Verify the columns were added
        print("\nVerifying columns...")
        cursor.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'crawl_jobs' 
            AND column_name IN ('anomalies_detected', 'scheduled_at', 'cron_schedule', 'duration_seconds')
            ORDER BY column_name
        """)
        
        results = cursor.fetchall()
        print("Found columns:")
        for column_name, data_type in results:
            print(f"  {column_name}: {data_type}")

    except Exception as e:
        print(f"Database connection error: {e}")
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    main()
