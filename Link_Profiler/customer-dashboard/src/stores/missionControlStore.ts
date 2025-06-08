import { create } from 'zustand'; // Added React import

// Define the structure of your real-time dashboard data
// This should match the DashboardRealtimeUpdates schema from your FastAPI backend
interface CrawlJobSummary {
  id: string;
  target_url: string;
  job_type: string;
  status: string;
  progress_percentage: number;
  created_at: string;
  started_date?: string;
  completed_date?: string;
  errors_count: number;
}

interface BacklinkDiscoveryMetrics {
  total_backlinks_discovered: number;
  unique_domains_discovered: number;
  new_backlinks_24h: number;
  avg_authority_score: number | null; // Changed to number | null
  top_linking_domains: string[];
  top_target_urls: string[];
  potential_spam_links_24h: number;
}

interface ApiPerformanceMetrics {
  total_calls: number;
  successful_calls: number;
  average_response_time_ms: number | null; // Changed to number | null
  success_rate: number | null; // Changed to number | null
  circuit_breaker_state: string; // e.g., "CLOSED", "OPEN", "HALF_OPEN"
}

interface ApiQuotaStatus {
  api_name: string;
  limit: number;
  used: number;
  remaining: number | null;
  reset_date: string; // ISO format string
  percentage_used: number | null; // Changed to number | null
  status: string;
  predicted_exhaustion_date: string | null;
  recommended_action: string | null;
  performance: ApiPerformanceMetrics; // Nested performance metrics
}

interface CrawlerMissionStatus {
  active_jobs_count: number;
  queued_jobs_count: number;
  completed_jobs_24h_count: number;
  failed_jobs_24h_count: number;
  total_pages_crawled_24h: number;
  queue_depth: number;
  active_satellites_count: number;
  total_satellites_count: number;
  satellite_utilization_percentage: number | null; // Changed to number | null
  avg_job_completion_time_seconds: number | null; // Changed to number | null
  recent_job_errors: any[]; // Adjust with actual CrawlError schema
}

interface AlertSummary {
  type: string;
  severity: string;
  message: string;
  timestamp: string; // ISO format string
  affected_jobs: string[] | null;
  recommended_action: string | null;
  details: any | null;
}

interface SatelliteFleetStatus {
  satellite_id: string;
  status: string; // Broadened from "active" | "idle" | "unresponsive" to string for flexibility
  last_heartbeat: string; // ISO format datetime string
  jobs_completed_24h: number;
  errors_24h: number;
  avg_job_duration_seconds: number | null;
  current_job_id: string | null;
  current_job_type: string | null;
  current_job_progress: number | null; // Percentage 0-100
}

interface DashboardRealtimeUpdates {
  timestamp: string; // ISO format string
  crawler_mission_status: CrawlerMissionStatus;
  backlink_discovery_metrics: BacklinkDiscoveryMetrics;
  api_quota_statuses: ApiQuotaStatus[]; // Changed from object to array
  domain_intelligence_metrics: DomainIntelligenceMetrics;
  performance_optimization_metrics: PerformanceOptimizationMetrics;
  alerts: AlertSummary[];
  satellite_fleet_status: SatelliteFleetStatus[]; // Changed to top-level array
}

interface MissionControlState {
  data: DashboardRealtimeUpdates | null;
  lastUpdated: string | null;
  setData: (newData: DashboardRealtimeUpdates) => void;
}

const useMissionControlStore = create<MissionControlState>((set) => ({
  data: null,
  lastUpdated: null,
  setData: (newData: DashboardRealtimeUpdates) => set({ data: newData, lastUpdated: newData.timestamp }), // Explicitly typed newData
}));

export default useMissionControlStore;
