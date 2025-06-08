export interface User {
  id: string;
  username: string;
  email: string;
  is_active: boolean;
  is_admin: boolean;
  created_at: string; // ISO format datetime string
  last_updated?: string; // ISO format datetime string
}

export interface Token {
  access_token: string;
  token_type: string;
}

export interface CrawlError {
  error_type: string;
  message: string;
  url?: string;
  details?: Record<string, any>;
  timestamp: string; // ISO format datetime string
}

export interface CrawlJob {
  id: string;
  targetUrl: string;
  status: string; // e.g., "QUEUED", "IN_PROGRESS", "COMPLETED", "FAILED"
  progress: number;
  created: string; // ISO format datetime string
  // Add other properties from your Python CrawlJob model as needed
  job_type: string;
  progress_percentage: number;
  urls_crawled: number;
  links_found: number;
  errors_count: number;
  error_log: CrawlError[];
  // Assuming these are ISO strings from Python datetime
  created_date: string;
  started_date?: string;
  completed_date?: string;
}

export interface ApiPerformanceMetrics {
  total_calls: number;
  successful_calls: number;
  average_response_time_ms: number | null;
  success_rate: number | null;
  circuit_breaker_state: string; // e.g., "CLOSED", "OPEN", "HALF_OPEN"
}

export interface ApiQuotaStatus {
  api_name: string;
  limit: number;
  used: number;
  remaining: number | null;
  reset_date: string; // ISO format string
  percentage_used: number | null;
  status: string; // e.g., "OK", "Warning", "Critical"
  predicted_exhaustion_date: string | null;
  recommended_action: string | null;
  performance: ApiPerformanceMetrics; // Nested performance metrics
}

export interface CrawlerMissionStatus {
  active_jobs_count: number;
  queued_jobs_count: number;
  completed_jobs_24h_count: number;
  failed_jobs_24h_count: number;
  total_pages_crawled_24h: number;
  queue_depth: number;
  active_satellites_count: number;
  total_satellites_count: number;
  satellite_utilization_percentage: number | null;
  avg_job_completion_time_seconds: number | null;
  recent_job_errors: CrawlError[];
}

export interface BacklinkDiscoveryMetrics {
  total_backlinks_discovered: number;
  unique_domains_discovered: number;
  new_backlinks_24h: number;
  avg_authority_score: number | null;
  top_linking_domains: string[];
  top_target_urls: string[];
  potential_spam_links_24h: number;
}

export interface DomainIntelligenceMetrics {
  total_domains_analyzed: number;
  valuable_expired_domains_found: number;
  avg_domain_value_score: number | null;
  new_domains_added_24h: number;
  top_niches_identified: string[];
}

export interface PerformanceOptimizationMetrics {
  avg_crawl_speed_pages_per_minute: number | null;
  avg_success_rate_percentage: number | null;
  avg_response_time_ms: number | null;
  bottlenecks_detected: string[];
  top_performing_satellites: string[];
  worst_performing_satellites: string[];
}

export interface DashboardAlert {
  alert_id: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  message: string;
  timestamp: string; // ISO format datetime string
  source: string;
  details?: Record<string, any>;
  is_resolved: boolean;
}

export interface SatelliteFleetStatus {
  satellite_id: string;
  status: 'active' | 'idle' | 'unresponsive';
  last_heartbeat: string; // ISO format datetime string
  jobs_completed_24h: number;
  errors_24h: number;
  avg_job_duration_seconds: number | null;
  current_job_id: string | null;
  current_job_type: string | null;
  current_job_progress: number | null; // Percentage 0-100
}

export interface DashboardRealtimeUpdates {
  timestamp: string; // ISO format string
  crawler_mission_status: CrawlerMissionStatus;
  backlink_discovery_metrics: BacklinkDiscoveryMetrics;
  api_quota_statuses: ApiQuotaStatus[];
  domain_intelligence_metrics: DomainIntelligenceMetrics;
  performance_optimization_metrics: PerformanceOptimizationMetrics;
  alerts: DashboardAlert[];
  satellite_fleet_status: SatelliteFleetStatus[];
}

// New interfaces for Settings.tsx
export interface SystemConfig {
  logging_level: string;
  api_cache_enabled: boolean;
  api_cache_ttl: number;
  crawler_max_depth: number;
  crawler_render_javascript: boolean;
  // Add other relevant config items here
}

export interface ApiKeyInfo {
  api_name: string;
  enabled: boolean;
  api_key_masked: string;
  monthly_limit: number;
  cost_per_unit: number;
}
