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
  average_response_time_ms: number;
  success_rate: number;
  circuit_breaker_state: string; // e.g., "CLOSED", "OPEN", "HALF_OPEN"
}

export interface ApiQuotaStatus {
  api_name: string;
  limit: number;
  used: number;
  remaining?: number | null; // null for unlimited, made optional
  reset_date: string; // ISO format string
  percentage_used: number;
  status: string; // e.g., "OK", "Warning", "Critical"
  predicted_exhaustion_date?: string | null; // ISO format string or null, made optional
  recommended_action?: string | null; // made optional
  performance?: ApiPerformanceMetrics; // Made optional to match potential backend omissions
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
  satellite_utilization_percentage: number;
  avg_job_completion_time_seconds: number;
  recent_job_errors: CrawlError[];
}

export interface BacklinkDiscoveryMetrics {
  total_backlinks_discovered: number;
  unique_domains_discovered: number;
  new_backlinks_24h: number;
  avg_authority_score: number;
  top_linking_domains: string[];
  top_target_urls: string[];
  potential_spam_links_24h: number;
}

export interface DomainIntelligenceMetrics {
  total_domains_analyzed: number;
  valuable_expired_domains_found: number;
  avg_domain_value_score: number;
  new_domains_added_24h: number;
  top_niches_identified: string[];
}

export interface PerformanceOptimizationMetrics {
  avg_crawl_speed_pages_per_minute: number;
  avg_success_rate_percentage: number;
  avg_response_time_ms: number;
  bottlenecks_detected: string[];
  top_performing_satellites: string[];
  worst_performing_satellites: string[];
}

export interface DashboardAlert {
  type: string;
  severity: string; // e.g., "CRITICAL", "WARNING", "INFO"
  message: string;
  timestamp: string; // ISO format datetime string
  affected_jobs?: string[];
  recommended_action?: string;
  details?: Record<string, any>;
}

export interface SatelliteFleetStatus {
  satellite_id: string;
  status: string; // Broadened from "active" | "idle" | "unresponsive" to string for flexibility
  last_heartbeat: string; // ISO format datetime string
  jobs_completed_24h: number;
  errors_24h: number;
  avg_job_duration_seconds?: number;
  current_job_id?: string;
  current_job_type?: string;
  current_job_progress?: number;
}

export interface DashboardRealtimeUpdates {
  timestamp: string; // ISO format datetime string
  crawler_mission_status: CrawlerMissionStatus;
  backlink_discovery_metrics: BacklinkDiscoveryMetrics;
  api_quota_statuses: ApiQuotaStatus[];
  domain_intelligence_metrics: DomainIntelligenceMetrics;
  performance_optimization_metrics: PerformanceOptimizationMetrics;
  alerts: DashboardAlert[];
  satellite_fleet_status: SatelliteFleetStatus[];
}
