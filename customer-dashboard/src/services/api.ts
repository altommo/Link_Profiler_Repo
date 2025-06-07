// customer-dashboard/src/services/api.ts
import { API_BASE_URL } from '../config';
import { User, Token } from '../types'; // Assuming User and Token types are defined in types.ts

const getAuthHeaders = (): HeadersInit => {
  const token = localStorage.getItem('access_token'); // Use 'access_token' for consistency
  return token ? { 'Authorization': `Bearer ${token}` } : {};
};

const handleResponse = async <T>(response: Response): Promise<T> => {
  if (!response.ok) {
    const errorData = await response.json();
    throw new Error(errorData.detail || 'Something went wrong');
  }
  return response.json() as Promise<T>;
};

export const loginUser = async (username: string, password: string): Promise<Token> => {
  const formData = new URLSearchParams();
  formData.append('username', username);
  formData.append('password', password);

  const response = await fetch(`${API_BASE_URL}/token`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
    },
    body: formData.toString(),
  });
  const data = await handleResponse<Token>(response);
  localStorage.setItem('access_token', data.access_token); // Use 'access_token' for consistency
  return data;
};

export const getUserProfile = async (): Promise<User> => {
  const response = await fetch(`${API_BASE_URL}/users/me`, {
    method: 'GET',
    headers: {
      ...getAuthHeaders(),
      'Content-Type': 'application/json',
    },
  });
  return handleResponse<User>(response);
};

export const updateProfile = async (profileData: Partial<User>): Promise<User> => {
  const response = await fetch(`${API_BASE_URL}/users/me`, {
    method: 'PUT', // Or PATCH, depending on your API
    headers: {
      ...getAuthHeaders(),
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(profileData),
  });
  return handleResponse<User>(response);
};

// Define a type for a simplified CrawlJob for the customer dashboard
interface CustomerCrawlJob {
  id: string;
  targetUrl: string;
  status: string;
  progress: number;
  created: string;
}

export const getCrawlJobs = async (): Promise<CustomerCrawlJob[]> => {
  // This endpoint would typically be customer-specific, e.g., /api/customer/jobs
  // Simulating data for now as the backend endpoint is not provided
  const simulatedData: CustomerCrawlJob[] = [
    { id: 'job-001', targetUrl: 'https://example.com', status: 'Completed', progress: 100, created: '2024-05-01' },
    { id: 'job-002', targetUrl: 'https://anothersite.org', status: 'In Progress', progress: 75, created: '2024-05-10' },
    { id: 'job-003', targetUrl: 'https://testdomain.net', status: 'Failed', progress: 20, created: '2024-05-15' },
    { id: 'job-004', targetUrl: 'https://newsite.io', status: 'Pending', progress: 0, created: '2024-05-20' },
  ];
  // In a real app:
  // const response = await fetch(`${API_BASE_URL}/customer/jobs`, { 
  //   method: 'GET',
  //   headers: {
  //     ...getAuthHeaders(),
  //     'Content-Type': 'application/json',
  //   },
  // });
  // return handleResponse<CustomerCrawlJob[]>(response);
  return Promise.resolve(simulatedData); // Return simulated data
};

export const submitCrawlJob = async (jobData: any): Promise<any> => {
  const response = await fetch(`${API_BASE_URL}/customer/submit_crawl`, {
    method: 'POST',
    headers: {
      ...getAuthHeaders(),
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(jobData),
  });
  return handleResponse<any>(response);
};

export const getUsageMetrics = async (): Promise<any> => {
  // This endpoint would typically be customer-specific, e.g., /api/customer/usage
  const response = await fetch(`${API_BASE_URL}/customer/usage`, {
    method: 'GET',
    headers: {
      ...getAuthHeaders(),
      'Content-Type': 'application/json',
    },
  });
  return handleResponse<any>(response);
};

// Add more API calls as needed for other dashboard features
