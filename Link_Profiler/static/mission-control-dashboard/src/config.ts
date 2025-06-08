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
  verify: `${API_BASE_URL}/users/me`, // Endpoint to get current user info
};

// Other configurations can go here
export const RECONNECT_INTERVAL_MS = 3000; // WebSocket reconnect interval
export const MAX_RECONNECT_ATTEMPTS = 10; // Max WebSocket reconnect attempts
