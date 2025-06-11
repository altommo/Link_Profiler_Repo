// src/config.ts

// Since the dashboard is served from the same origin as the API,
// we can use relative URLs for API calls
export const API_BASE_URL = '';
export const WS_BASE_URL = window.location.protocol === 'https:' ? 
  `wss://${window.location.host}` : 
  `ws://${window.location.host}`;

export const AUTH_ENDPOINTS = {
  login: `${API_BASE_URL}/token`,
  register: `${API_BASE_URL}/register`,
  verify: `${API_BASE_URL}/users/me`,
};

// Customer-specific API endpoints
export const CUSTOMER_ENDPOINTS = {
  // Job management
  jobs: `${API_BASE_URL}/jobs`,
  createJob: `${API_BASE_URL}/jobs/create`,
  jobStatus: (jobId: string) => `${API_BASE_URL}/jobs/${jobId}`,
  
  // Link analysis
  linkProfile: (url: string) => `${API_BASE_URL}/link_profile/${encodeURIComponent(url)}`,
  domainInfo: (domain: string) => `${API_BASE_URL}/domain/info/${domain}`,
  
  // Reports
  reports: `${API_BASE_URL}/reports`,
  createReport: `${API_BASE_URL}/reports/create`,
  
  // Analytics
  analytics: `${API_BASE_URL}/analytics`,
  competitiveAnalysis: `${API_BASE_URL}/competitive-analysis`,
  
  // WebSocket for real-time updates
  websocket: `${WS_BASE_URL}/ws/customer`,
};

// Other configurations
export const RECONNECT_INTERVAL_MS = 3000;
export const MAX_RECONNECT_ATTEMPTS = 10;
export const POLLING_INTERVAL_MS = 30000; // 30 seconds for job status polling
