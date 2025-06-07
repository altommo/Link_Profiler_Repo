// src/config.ts

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
export const WS_BASE_URL = import.meta.env.VITE_WS_BASE_URL || 'ws://localhost:8000';

export const AUTH_ENDPOINTS = {
  login: `${API_BASE_URL}/token`,
  register: `${API_BASE_URL}/register`,
  verify: `${API_BASE_URL}/users/me`, // Endpoint to get current user info
};

// Other configurations can go here
export const RECONNECT_INTERVAL_MS = 3000; // WebSocket reconnect interval
export const MAX_RECONNECT_ATTEMPTS = 10; // Max WebSocket reconnect attempts
