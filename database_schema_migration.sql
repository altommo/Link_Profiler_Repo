-- Comprehensive Database Schema Fix for Link Profiler
-- This script ensures all required columns exist with proper data types
-- Run this script with: psql -d link_profiler_db -f database_schema_migration.sql

-- Function to safely add columns if they don't exist
CREATE OR REPLACE FUNCTION add_column_if_not_exists(
    table_name TEXT,
    column_name TEXT,
    column_type TEXT,
    default_value TEXT DEFAULT NULL
) RETURNS VOID AS $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = table_name AND column_name = column_name
    ) THEN
        IF default_value IS NOT NULL THEN
            EXECUTE format('ALTER TABLE %I ADD COLUMN %I %s DEFAULT %s', 
                         table_name, column_name, column_type, default_value);
        ELSE
            EXECUTE format('ALTER TABLE %I ADD COLUMN %I %s', 
                         table_name, column_name, column_type);
        END IF;
        RAISE NOTICE 'Added column % to table %', column_name, table_name;
    ELSE
        RAISE NOTICE 'Column % already exists in table %', column_name, table_name;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Fix crawl_jobs table
SELECT add_column_if_not_exists('crawl_jobs', 'errors', 'JSONB', '''[]''');
SELECT add_column_if_not_exists('crawl_jobs', 'created_at', 'TIMESTAMP', 'CURRENT_TIMESTAMP');
SELECT add_column_if_not_exists('crawl_jobs', 'config', 'JSONB', '''{}''');

-- Fix users table (ensure all required fields exist)
SELECT add_column_if_not_exists('users', 'role', 'VARCHAR(50)', '''user''');
SELECT add_column_if_not_exists('users', 'organization_id', 'VARCHAR(255)');
SELECT add_column_if_not_exists('users', 'last_updated', 'TIMESTAMP', 'CURRENT_TIMESTAMP');
SELECT add_column_if_not_exists('users', 'last_fetched_at', 'TIMESTAMP', 'CURRENT_TIMESTAMP');

-- Ensure created_at is populated if created_date exists
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'crawl_jobs' AND column_name = 'created_date'
    ) AND EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'crawl_jobs' AND column_name = 'created_at'
    ) THEN
        UPDATE crawl_jobs 
        SET created_at = created_date 
        WHERE created_at IS NULL AND created_date IS NOT NULL;
        RAISE NOTICE 'Copied created_date to created_at for crawl_jobs';
    END IF;
END $$;

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_crawl_jobs_created_at ON crawl_jobs(created_at);
CREATE INDEX IF NOT EXISTS idx_crawl_jobs_status ON crawl_jobs(status);
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

-- Verify the fixes
SELECT 'crawl_jobs columns:' as info;
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns 
WHERE table_name = 'crawl_jobs' 
ORDER BY ordinal_position;

SELECT 'users columns:' as info;
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns 
WHERE table_name = 'users' 
ORDER BY ordinal_position;

-- Clean up the function
DROP FUNCTION add_column_if_not_exists(TEXT, TEXT, TEXT, TEXT);

-- Show summary
SELECT 
    'Summary:' as info,
    (SELECT COUNT(*) FROM crawl_jobs) as total_crawl_jobs,
    (SELECT COUNT(*) FROM users) as total_users;
