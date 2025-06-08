// src/types.ts

// --- Core Data Models (from Link_Profiler/core/models.py) ---
export interface User {
  user_id: string;
  username: string;
  email: string;
  is_admin: boolean;
  created_date: string; // ISO format datetime string
  updated_date: string; // ISO format datetime string
  last_login?: string; // ISO format datetime string
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

// --- API Schemas (from Link_Profiler/api/schemas.py) ---

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
  remaining: number | null; // null for unlimited
  reset_date: string; // ISO format datetime string
  percentage_used: number;
  status: string; // e.g., "OK", "Warning", "Critical"
  predicted_exhaustion_date: string | null; // ISO format datetime string
  recommended_action: string | null;
  performance: ApiPerformanceMetrics;
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
  timestamp: string; // ISO format datetime string
  crawler_mission_status: CrawlerMissionStatus;
  backlink_discovery_metrics: BacklinkDiscoveryMetrics;
  api_quota_statuses: ApiQuotaStatus[];
  domain_intelligence_metrics: DomainIntelligenceMetrics;
  performance_optimization_metrics: PerformanceOptimizationMetrics;
  alerts: DashboardAlert[];
  satellite_fleet_status: SatelliteFleetStatus[];
}

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
