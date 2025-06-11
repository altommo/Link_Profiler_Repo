// src/types.ts

export interface User {
  id: string;
  username: string;
  email: string;
  is_active: boolean;
  is_admin: boolean;
  role: string;
  organization_id?: string;
  created_at: string;
  last_updated?: string;
}

export interface Token {
  access_token: string;
  token_type: string;
}

// Job Management Types
export interface CrawlJob {
  id: string;
  target_url: string;
  job_type: string;
  status: 'QUEUED' | 'IN_PROGRESS' | 'COMPLETED' | 'FAILED' | 'CANCELLED';
  progress_percentage: number;
  urls_crawled: number;
  links_found: number;
  errors: CrawlError[];
  priority: number;
  scheduled_at?: string;
  cron_schedule?: string;
  created_at: string;
  started_date?: string;
  completed_date?: string;
  config?: Record<string, any>;
}

export interface CrawlError {
  error_type: string;
  message: string;
  url?: string;
  details?: Record<string, any>;
  timestamp: string;
}

export interface JobCreateRequest {
  target_url: string;
  job_type: 'crawl' | 'link_analysis' | 'competitive_analysis' | 'domain_analysis';
  priority?: number;
  config?: {
    max_depth?: number;
    max_pages?: number;
    respect_robots_txt?: boolean;
    extract_images?: boolean;
    extract_pdfs?: boolean;
  };
}

// Link Analysis Types
export interface LinkProfile {
  id: string;
  target_url: string;
  total_backlinks: number;
  unique_domains: number;
  authority_score: number;
  spam_score: number;
  status: string;
  last_updated: string;
  backlinks: Backlink[];
}

export interface Backlink {
  id: string;
  source_url: string;
  target_url: string;
  anchor_text: string;
  link_type: 'follow' | 'nofollow';
  authority_score: number;
  spam_level: 'low' | 'medium' | 'high';
  first_seen: string;
  last_seen: string;
  is_active: boolean;
}

// Domain Analysis Types
export interface Domain {
  name: string;
  registrar: string;
  creation_date: string;
  expiration_date: string;
  nameservers: string[];
  whois_data: Record<string, any>;
  authority_metrics: {
    domain_authority: number;
    page_authority: number;
    trust_flow: number;
    citation_flow: number;
  };
  technical_metrics: {
    ssl_enabled: boolean;
    response_time_ms: number;
    mobile_friendly: boolean;
    security_issues: string[];
  };
}

// Analytics Types
export interface AnalyticsData {
  date_range: {
    start_date: string;
    end_date: string;
  };
  metrics: {
    total_jobs: number;
    completed_jobs: number;
    failed_jobs: number;
    total_backlinks_found: number;
    unique_domains_analyzed: number;
    average_authority_score: number;
  };
  trends: {
    daily_jobs: Array<{
      date: string;
      jobs_created: number;
      jobs_completed: number;
    }>;
    domain_authority_trend: Array<{
      date: string;
      average_da: number;
    }>;
  };
}

// Competitive Analysis Types
export interface CompetitiveAnalysisResult {
  id: string;
  user_domain: string;
  competitor_domains: string[];
  analysis_type: string;
  results: {
    backlink_gap: BacklinkGap[];
    keyword_opportunities: KeywordOpportunity[];
    content_gaps: ContentGap[];
  };
  created_at: string;
  status: 'PENDING' | 'IN_PROGRESS' | 'COMPLETED' | 'FAILED';
}

export interface BacklinkGap {
  competitor_domain: string;
  unique_backlinks: number;
  shared_backlinks: number;
  opportunity_score: number;
  top_opportunities: Array<{
    source_domain: string;
    authority_score: number;
    relevance_score: number;
  }>;
}

export interface KeywordOpportunity {
  keyword: string;
  search_volume: number;
  difficulty: number;
  user_ranking?: number;
  competitor_rankings: Array<{
    domain: string;
    ranking: number;
  }>;
  opportunity_score: number;
}

export interface ContentGap {
  topic: string;
  competitor_coverage: number;
  user_coverage: number;
  opportunity_score: number;
  recommended_content_type: string;
}

// Report Types
export interface Report {
  id: string;
  title: string;
  report_type: 'link_analysis' | 'domain_audit' | 'competitive_analysis' | 'comprehensive';
  status: 'PENDING' | 'GENERATING' | 'COMPLETED' | 'FAILED';
  created_at: string;
  completed_at?: string;
  file_url?: string;
  parameters: Record<string, any>;
}

// Dashboard State Types
export interface DashboardStats {
  total_jobs: number;
  active_jobs: number;
  completed_jobs_today: number;
  total_backlinks_discovered: number;
  domains_analyzed: number;
  average_authority_score: number;
  recent_activity: RecentActivity[];
}

export interface RecentActivity {
  id: string;
  type: 'job_completed' | 'report_generated' | 'analysis_finished';
  title: string;
  description: string;
  timestamp: string;
  status: 'success' | 'warning' | 'error';
}

// Notification Types
export interface Notification {
  id: string;
  type: 'info' | 'success' | 'warning' | 'error';
  title: string;
  message: string;
  timestamp: string;
  read: boolean;
  action_url?: string;
}

// Customer-specific UI Types
export interface QuickAction {
  id: string;
  title: string;
  description: string;
  icon: string;
  action: () => void;
  disabled?: boolean;
}

export interface ChartDataPoint {
  date: string;
  value: number;
  label?: string;
}
