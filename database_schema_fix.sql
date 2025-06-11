-- Database Schema Fix Script for Link Profiler
-- Run this to fix the created_at vs created_date issue

-- First, check what columns exist in crawl_jobs table
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'crawl_jobs' 
ORDER BY ordinal_position;

-- If the table has 'created_date' but ORM expects 'created_at', add the column
-- (This is a safe operation that won't break existing functionality)
DO $$
BEGIN
    -- Check if created_at column exists
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'crawl_jobs' AND column_name = 'created_at'
    ) THEN
        -- If created_date exists, copy its values to created_at
        IF EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_name = 'crawl_jobs' AND column_name = 'created_date'
        ) THEN
            ALTER TABLE crawl_jobs ADD COLUMN created_at TIMESTAMP;
            UPDATE crawl_jobs SET created_at = created_date WHERE created_date IS NOT NULL;
            RAISE NOTICE 'Added created_at column and copied data from created_date';
        ELSE
            -- Neither column exists, create created_at with default
            ALTER TABLE crawl_jobs ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
            RAISE NOTICE 'Added created_at column with default timestamp';
        END IF;
    ELSE
        RAISE NOTICE 'created_at column already exists';
    END IF;
END
$$;

-- Verify the fix
SELECT 
    'crawl_jobs' as table_name,
    COUNT(*) as total_rows,
    COUNT(created_at) as rows_with_created_at,
    COUNT(created_date) as rows_with_created_date
FROM crawl_jobs;

-- Check users table structure
SELECT column_name, data_type, is_nullable
FROM information_schema.columns 
WHERE table_name = 'users' 
ORDER BY ordinal_position;

-- Create index on created_at for better performance
CREATE INDEX IF NOT EXISTS idx_crawl_jobs_created_at ON crawl_jobs(created_at);

-- Show final structure
\d crawl_jobs;