"""
Prometheus Metrics - Defines and exposes custom metrics for the Link Profiler.
File: Link_Profiler/monitoring/prometheus_metrics.py
"""

from prometheus_client import Counter, Gauge, Histogram, generate_latest

# --- API Metrics ---
# Counter for total API requests
API_REQUESTS_TOTAL = Counter(
    'link_profiler_api_requests_total',
    'Total number of API requests received',
    ['endpoint', 'method', 'status_code']
)

# Histogram for API request duration
API_REQUEST_DURATION_SECONDS = Histogram(
    'link_profiler_api_request_duration_seconds',
    'Duration of API requests in seconds',
    ['endpoint', 'method']
)

# --- Job Metrics ---
# Counter for total jobs created
JOBS_CREATED_TOTAL = Counter(
    'link_profiler_jobs_created_total',
    'Total number of jobs created',
    ['job_type']
)

# Counter for jobs completed successfully
JOBS_COMPLETED_SUCCESS_TOTAL = Counter(
    'link_profiler_jobs_completed_success_total',
    'Total number of jobs completed successfully',
    ['job_type']
)

# Counter for jobs failed
JOBS_FAILED_TOTAL = Counter(
    'link_profiler_jobs_failed_total',
    'Total number of jobs that failed',
    ['job_type']
)

# Gauge for current number of in-progress jobs
JOBS_IN_PROGRESS = Gauge(
    'link_profiler_jobs_in_progress',
    'Current number of jobs in progress',
    ['job_type']
)

# Gauge for current number of pending jobs
JOBS_PENDING = Gauge(
    'link_profiler_jobs_pending',
    'Current number of jobs pending',
    ['job_type']
)

# Counter for total URLs crawled
CRAWLED_URLS_TOTAL = Counter(
    'link_profiler_crawled_urls_total',
    'Total number of URLs crawled by all crawlers',
    ['job_type']
)

# Counter for total backlinks found
BACKLINKS_FOUND_TOTAL = Counter(
    'link_profiler_backlinks_found_total',
    'Total number of backlinks discovered',
    ['job_type']
)

# Counter for total errors logged in jobs
JOB_ERRORS_TOTAL = Counter(
    'link_profiler_job_errors_total',
    'Total number of errors logged within jobs',
    ['job_type', 'error_type']
)

# --- Database Metrics (can be extended) ---
# Counter for database write operations
DB_WRITES_TOTAL = Counter(
    'link_profiler_db_writes_total',
    'Total number of database write operations',
    ['table']
)

# Counter for database read operations
DB_READS_TOTAL = Counter(
    'link_profiler_db_reads_total',
    'Total number of database read operations',
    ['table']
)

# Counter for all database operations with status
DB_OPERATIONS_TOTAL = Counter(
    'link_profiler_db_operations_total',
    'Total number of database operations grouped by type and status',
    ['operation_type', 'table_name', 'status']
)

# Histogram for measuring query duration
DB_QUERY_DURATION_SECONDS = Histogram(
    'link_profiler_db_query_duration_seconds',
    'Duration of database queries in seconds',
    ['query_type', 'table_name']
)

# --- Redis Metrics (can be extended) ---
# Gauge for Redis queue size
REDIS_QUEUE_SIZE = Gauge(
    'link_profiler_redis_queue_size',
    'Current size of Redis job queues',
    ['queue_name']
)

# Counter for messages pushed to Redis queues
REDIS_MESSAGES_PUSHED_TOTAL = Counter(
    'link_profiler_redis_messages_pushed_total',
    'Total messages pushed to Redis queues',
    ['queue_name']
)

# Counter for messages popped from Redis queues
REDIS_MESSAGES_POPPED_TOTAL = Counter(
    'link_profiler_redis_messages_popped_total',
    'Total messages popped from Redis queues',
    ['queue_name']
)

# --- External API Call Metrics ---
# Counter for external API calls
EXTERNAL_API_CALLS_TOTAL = Counter(
    'link_profiler_external_api_calls_total',
    'Total number of calls to external APIs',
    ['service', 'api_client_type', 'endpoint']
)

# Histogram for external API call duration
EXTERNAL_API_CALL_DURATION_SECONDS = Histogram(
    'link_profiler_external_api_call_duration_seconds',
    'Duration of external API calls in seconds',
    ['service', 'api_client_type', 'endpoint']
)

# Counter for external API call errors
EXTERNAL_API_CALL_ERRORS_TOTAL = Counter(
    'link_profiler_external_api_call_errors_total',
    'Total number of errors from external API calls',
    ['service', 'api_client_type', 'endpoint', 'status_code']
)

# Counter for rate limiter throttles
API_RATE_LIMITER_THROTTLES_TOTAL = Counter(
    'link_profiler_api_rate_limiter_throttles_total',
    'Total number of times an API call was throttled by the rate limiter',
    ['service', 'api_client_type', 'endpoint']
)

# Counter for API call retries
EXTERNAL_API_CALL_RETRIES_TOTAL = Counter(
    'link_profiler_external_api_call_retries_total',
    'Total number of retries for external API calls',
    ['service', 'api_client_type', 'endpoint']
)

# --- API Cache Metrics ---
API_CACHE_HITS_TOTAL = Counter(
    'link_profiler_api_cache_hits_total',
    'Total number of API cache hits',
    ['service', 'endpoint']
)

API_CACHE_MISSES_TOTAL = Counter(
    'link_profiler_api_cache_misses_total',
    'Total number of API cache misses',
    ['service', 'endpoint']
)

API_CACHE_SET_TOTAL = Counter(
    'link_profiler_api_cache_set_total',
    'Total number of times an API response was cached',
    ['service', 'endpoint']
)

API_CACHE_ERRORS_TOTAL = Counter(
    'link_profiler_api_cache_errors_total',
    'Total number of errors encountered during API caching operations',
    ['service', 'endpoint', 'error_type']
)

# --- Dashboard Alert Metrics ---
DASHBOARD_ALERTS_GAUGE = Gauge(
    'link_profiler_dashboard_alerts_active',
    'Current number of active dashboard alerts',
    ['alert_type', 'severity']
)

DASHBOARD_ALERTS_TOTAL = Counter(
    'link_profiler_dashboard_alerts_total',
    'Total number of dashboard alerts triggered',
    ['alert_type', 'severity']
)

# --- Mission Control Dashboard Specific Metrics ---
DASHBOARD_MODULE_REFRESH_DURATION_SECONDS = Histogram(
    'link_profiler_dashboard_module_refresh_duration_seconds',
    'Duration of individual dashboard module data refreshes',
    ['module_name']
)

# --- Utility function to expose metrics ---
def get_metrics_text():
    """Returns the current metrics in Prometheus text format."""
    return generate_latest().decode('utf-8')
