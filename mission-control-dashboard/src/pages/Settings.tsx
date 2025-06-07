import React, { useState, useEffect } from 'react';
import DataCard from '../components/ui/DataCard';
import { API_BASE_URL } from '../config'; // Assuming API_BASE_URL is defined here
import { SystemConfig, User, ApiKeyInfo } from '../types'; // Assuming these types are defined

const Settings: React.FC = () => {
  const [systemConfig, setSystemConfig] = useState<SystemConfig | null>(null);
  const [users, setUsers] = useState<User[]>([]);
  const [apiKeys, setApiKeys] = useState<ApiKeyInfo[]>([]);
  const [auditLogs, setAuditLogs] = useState<any[]>([]); // Define a proper type for audit logs
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const token = localStorage.getItem('access_token'); // Get token from local storage

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      if (!token) {
        throw new Error("Authentication token not found. Please log in.");
      }

      const headers = {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      };

      // Fetch System Config
      const configResponse = await fetch(`${API_BASE_URL}/admin/config`, { headers });
      if (!configResponse.ok) throw new Error(`Failed to fetch system config: ${configResponse.statusText}`);
      setSystemConfig(await configResponse.json());

      // Fetch Users
      const usersResponse = await fetch(`${API_BASE_URL}/admin/users`, { headers });
      if (!usersResponse.ok) throw new Error(`Failed to fetch users: ${usersResponse.statusText}`);
      setUsers(await usersResponse.json());

      // Fetch API Keys
      const apiKeysResponse = await fetch(`${API_BASE_URL}/admin/api_keys`, { headers });
      if (!apiKeysResponse.ok) throw new Error(`Failed to fetch API keys: ${apiKeysResponse.statusText}`);
      setApiKeys(await apiKeysResponse.json());

      // Fetch Audit Logs
      const auditLogsResponse = await fetch(`${API_BASE_URL}/admin/audit_logs`, { headers });
      if (!auditLogsResponse.ok) throw new Error(`Failed to fetch audit logs: ${auditLogsResponse.statusText}`);
      setAuditLogs(await auditLogsResponse.json());

    } catch (err: any) {
      setError(err.message);
      console.error("Error fetching settings data:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [token]); // Re-fetch if token changes

  const handleConfigChange = async (key: keyof SystemConfig, value: any) => {
    try {
      if (!token) throw new Error("Authentication token not found.");
      const response = await fetch(`${API_BASE_URL}/admin/config`, {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ [key]: value }),
      });
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || `Failed to update config for ${key}`);
      }
      alert(`Configuration for ${key} updated successfully.`);
      fetchData(); // Refresh data
    } catch (err: any) {
      alert(`Error updating config: ${err.message}`);
      console.error(`Error updating config ${key}:`, err);
    }
  };

  const handleUserAction = async (userId: string, action: 'delete' | 'update', userData?: Partial<User>) => {
    try {
      if (!token) throw new Error("Authentication token not found.");
      let response;
      if (action === 'delete') {
        if (!window.confirm(`Are you sure you want to delete user ${userId}?`)) return;
        response = await fetch(`${API_BASE_URL}/admin/users/${userId}`, {
          method: 'DELETE',
          headers: { 'Authorization': `Bearer ${token}` },
        });
      } else if (action === 'update' && userData) {
        response = await fetch(`${API_BASE_URL}/admin/users/${userId}`, {
          method: 'PUT',
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(userData),
        });
      }
      
      if (!response || !response.ok) {
        const errorData = await response?.json();
        throw new Error(errorData?.detail || `Failed to ${action} user`);
      }
      alert(`User ${userId} ${action}d successfully.`);
      fetchData();
    } catch (err: any) {
      alert(`Error ${action}ing user: ${err.message}`);
      console.error(`Error ${action}ing user ${userId}:`, err);
    }
  };

  const handleApiKeyUpdate = async (apiName: string, newKey: string) => {
    try {
      if (!token) throw new Error("Authentication token not found.");
      const response = await fetch(`${API_BASE_URL}/admin/api_keys/${apiName}/update`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ new_key: newKey }),
      });
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || `Failed to update API key for ${apiName}`);
      }
      alert(`API key for ${apiName} updated successfully.`);
      fetchData();
    } catch (err: any) {
      alert(`Error updating API key: ${err.message}`);
      console.error(`Error updating API key for ${apiName}:`, err);
    }
  };


  if (loading) {
    return (
      <div className="text-center text-nasa-light-gray text-xl mt-20">
        <p>Loading system settings...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center text-red-500 text-xl mt-20">
        <p>Error: {error}</p>
        <p className="text-sm text-nasa-light-gray mt-2">Please ensure you are logged in as an administrator.</p>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <h1 className="text-4xl font-bold text-nasa-cyan mb-4">System Settings</h1>

      {/* General Configuration */}
      <DataCard title="General Configuration">
        {systemConfig ? (
          <div className="space-y-4 text-nasa-light-gray">
            <div>
              <label className="block text-sm font-bold mb-1">Logging Level:</label>
              <select
                className="form-select"
                value={systemConfig.logging_level}
                onChange={(e) => handleConfigChange('logging_level', e.target.value)}
              >
                <option value="DEBUG">DEBUG</option>
                <option value="INFO">INFO</option>
                <option value="WARNING">WARNING</option>
                <option value="ERROR">ERROR</option>
                <option value="CRITICAL">CRITICAL</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-bold mb-1">API Cache Enabled:</label>
              <input
                type="checkbox"
                checked={systemConfig.api_cache_enabled}
                onChange={(e) => handleConfigChange('api_cache_enabled', e.target.checked)}
                className="form-checkbox h-5 w-5 text-nasa-cyan rounded"
              />
            </div>
            <div>
              <label className="block text-sm font-bold mb-1">API Cache TTL (seconds):</label>
              <input
                type="number"
                value={systemConfig.api_cache_ttl}
                onChange={(e) => handleConfigChange('api_cache_ttl', parseInt(e.target.value))}
                className="form-input"
              />
            </div>
            <div>
              <label className="block text-sm font-bold mb-1">Crawler Max Depth:</label>
              <input
                type="number"
                value={systemConfig.crawler_max_depth}
                onChange={(e) => handleConfigChange('crawler_max_depth', parseInt(e.target.value))}
                className="form-input"
              />
            </div>
            <div>
              <label className="block text-sm font-bold mb-1">Crawler Render Javascript:</label>
              <input
                type="checkbox"
                checked={systemConfig.crawler_render_javascript}
                onChange={(e) => handleConfigChange('crawler_render_javascript', e.target.checked)}
                className="form-checkbox h-5 w-5 text-nasa-cyan rounded"
              />
            </div>
          </div>
        ) : (
          <p className="text-nasa-light-gray">No general configuration available.</p>
        )}
      </DataCard>

      {/* User Management */}
      <DataCard title="User Management">
        <div className="max-h-96 overflow-y-auto pr-2">
          {users.length > 0 ? (
            <table className="w-full text-left text-nasa-light-gray text-sm">
              <thead>
                <tr className="text-nasa-cyan border-b border-nasa-light-gray">
                  <th className="py-2 px-4">Username</th>
                  <th className="py-2 px-4">Email</th>
                  <th className="py-2 px-4">Admin</th>
                  <th className="py-2 px-4">Actions</th>
                </tr>
              </thead>
              <tbody>
                {users.map((user) => (
                  <tr key={user.user_id} className="border-b border-gray-700">
                    <td className="py-2 px-4">{user.username}</td>
                    <td className="py-2 px-4">{user.email}</td>
                    <td className="py-2 px-4">{user.is_admin ? 'Yes' : 'No'}</td>
                    <td className="py-2 px-4 space-x-1">
                      <button className="btn-xs btn-secondary" onClick={() => alert('Edit functionality to be implemented')}>Edit</button>
                      <button className="btn-xs btn-danger" onClick={() => handleUserAction(user.user_id, 'delete')}>Delete</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="text-nasa-light-gray text-sm">No users found.</p>
          )}
        </div>
        <button className="btn-primary mt-4" onClick={() => alert('Add User functionality to be implemented')}>Add New User</button>
      </DataCard>

      {/* API Key Management */}
      <DataCard title="API Key Management">
        <div className="max-h-96 overflow-y-auto pr-2">
          {apiKeys.length > 0 ? (
            <table className="w-full text-left text-nasa-light-gray text-sm">
              <thead>
                <tr className="text-nasa-cyan border-b border-nasa-light-gray">
                  <th className="py-2 px-4">API Name</th>
                  <th className="py-2 px-4">Enabled</th>
                  <th className="py-2 px-4">Key (Masked)</th>
                  <th className="py-2 px-4">Monthly Limit</th>
                  <th className="py-2 px-4">Cost/Unit</th>
                  <th className="py-2 px-4">Actions</th>
                </tr>
              </thead>
              <tbody>
                {apiKeys.map((keyInfo) => (
                  <tr key={keyInfo.api_name} className="border-b border-gray-700">
                    <td className="py-2 px-4">{keyInfo.api_name}</td>
                    <td className="py-2 px-4">{keyInfo.enabled ? 'Yes' : 'No'}</td>
                    <td className="py-2 px-4">{keyInfo.api_key_masked}</td>
                    <td className="py-2 px-4">{keyInfo.monthly_limit === -1 ? 'Unlimited' : keyInfo.monthly_limit}</td>
                    <td className="py-2 px-4">{keyInfo.cost_per_unit}</td>
                    <td className="py-2 px-4">
                      <button className="btn-xs btn-secondary" onClick={() => {
                        const newKey = prompt(`Enter new API key for ${keyInfo.api_name}:`);
                        if (newKey) handleApiKeyUpdate(keyInfo.api_name, newKey);
                      }}>Update Key</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="text-nasa-light-gray text-sm">No API keys configured.</p>
          )}
        </div>
      </DataCard>

      {/* Audit Logs */}
      <DataCard title="Audit Logs">
        <div className="max-h-96 overflow-y-auto pr-2">
          {auditLogs.length > 0 ? (
            <table className="w-full text-left text-nasa-light-gray text-sm">
              <thead>
                <tr className="text-nasa-cyan border-b border-nasa-light-gray">
                  <th className="py-2 px-4">Timestamp</th>
                  <th className="py-2 px-4">User</th>
                  <th className="py-2 px-4">Action</th>
                  <th className="py-2 px-4">Details</th>
                </tr>
              </thead>
              <tbody>
                {auditLogs.map((log, index) => (
                  <tr key={index} className="border-b border-gray-700">
                    <td className="py-2 px-4">{new Date(log.timestamp).toLocaleString()}</td>
                    <td className="py-2 px-4">{log.user}</td>
                    <td className="py-2 px-4">{log.action}</td>
                    <td className="py-2 px-4">
                      <pre className="text-xs bg-gray-800 p-1 rounded overflow-x-auto">{JSON.stringify(log.details, null, 2)}</pre>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="text-nasa-light-gray text-sm">No audit logs found.</p>
          )}
        </div>
      </DataCard>
    </div>
  );
};

export default Settings;
