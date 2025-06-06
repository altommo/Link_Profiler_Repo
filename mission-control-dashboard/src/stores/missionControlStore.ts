import { create } from 'zustand';

// Define the structure of your real-time dashboard data
// This should match the DashboardRealtimeUpdates schema from your FastAPI backend
interface DashboardRealtimeUpdates {
  timestamp: string; // ISO format string
  crawler_mission_status: {
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
    recent_job_errors: any[]; // Adjust with actual CrawlError schema
  };
  backlink_discovery_metrics: {
    total_backlinks_discovered: number;
    unique_domains_discovered: number;
    new_backlinks_24h: number;
    avg_authority_score: number;
    top_linking_domains: string[];
    top_target_urls: string[];
    potential_spam_links_24h: number;
  };
  api_quota_statuses: {
    api_name: string;
    limit: number;
    used: number;
    remaining: number;
    reset_date: string; // ISO format string
    percentage_used: number;
    status: string;
    predicted_exhaustion_date: string | null; // ISO format string or null
    recommended_action: string | null;
  }[];
  domain_intelligence_metrics: {
    total_domains_analyzed: number;
    valuable_expired_domains_found: number;
    avg_domain_value_score: number;
    new_domains_added_24h: number;
    top_niches_identified: string[];
  };
  performance_optimization_metrics: {
    avg_crawl_speed_pages_per_minute: number;
    avg_success_rate_percentage: number;
    avg_response_time_ms: number;
    bottlenecks_detected: string[];
    top_performing_satellites: string[];
    worst_performing_satellites: string[];
  };
  alerts: {
    type: string;
    severity: string;
    message: string;
    timestamp: string; // ISO format string
    affected_jobs: string[] | null;
    recommended_action: string | null;
    details: any | null;
  }[];
  satellite_fleet_status: {
    satellite_id: string;
    status: string;
    last_heartbeat: string; // ISO format string
    jobs_completed_24h: number;
    errors_24h: number;
    avg_job_duration_seconds: number | null;
    current_job_id: string | null;
    current_job_type: string | null;
    current_job_progress: number | null;
  }[];
}

interface MissionControlState {
  data: DashboardRealtimeUpdates | null;
  lastUpdated: string | null;
  setData: (newData: DashboardRealtimeUpdates) => void;
}

const useMissionControlStore = create<MissionControlState>((set) => ({
  data: null,
  lastUpdated: null,
  setData: (newData) => set({ data: newData, lastUpdated: newData.timestamp }),
}));

export default useMissionControlStore;
