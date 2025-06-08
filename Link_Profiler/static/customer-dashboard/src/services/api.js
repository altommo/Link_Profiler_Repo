// customer-dashboard/src/services/api.js

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api';

const getAuthHeaders = () => {
  const token = localStorage.getItem('token'); // Or wherever you store your JWT
  return token ? { 'Authorization': `Bearer ${token}` } : {};
};

const handleResponse = async (response) => {
  if (!response.ok) {
    const errorData = await response.json();
    throw new Error(errorData.detail || 'Something went wrong');
  }
  return response.json();
};

export const loginUser = async (username, password) => {
  const response = await fetch(`${API_BASE_URL}/token`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
    },
    body: new URLSearchParams({ username, password }).toString(),
  });
  const data = await handleResponse(response);
  // Assuming the API returns { access_token: "...", token_type: "bearer" }
  localStorage.setItem('token', data.access_token);
  return data;
};

export const getUserProfile = async () => {
  const response = await fetch(`${API_BASE_URL}/users/me`, {
    method: 'GET',
    headers: {
      ...getAuthHeaders(),
      'Content-Type': 'application/json',
    },
  });
  return handleResponse(response);
};

export const updateProfile = async (profileData) => {
  const response = await fetch(`${API_BASE_URL}/users/me`, {
    method: 'PUT', // Or PATCH, depending on your API
    headers: {
      ...getAuthHeaders(),
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(profileData),
  });
  return handleResponse(response);
};

export const getCrawlJobs = async () => {
  // This endpoint would typically be customer-specific, e.g., /api/customer/jobs
  const response = await fetch(`${API_BASE_URL}/customer/jobs`, { 
    method: 'GET',
    headers: {
      ...getAuthHeaders(),
      'Content-Type': 'application/json',
    },
  });
  return handleResponse(response);
};

export const submitCrawlJob = async (jobData) => {
  const response = await fetch(`${API_BASE_URL}/customer/submit_crawl`, {
    method: 'POST',
    headers: {
      ...getAuthHeaders(),
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(jobData),
  });
  return handleResponse(response);
};

export const getUsageMetrics = async () => {
  // This endpoint would typically be customer-specific, e.g., /api/customer/usage
  const response = await fetch(`${API_BASE_URL}/customer/usage`, {
    method: 'GET',
    headers: {
      ...getAuthHeaders(),
      'Content-Type': 'application/json',
    },
  });
  return handleResponse(response);
};

// Add more API calls as needed for other dashboard features
