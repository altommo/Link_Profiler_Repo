import React, { useState, useEffect } from 'react';
import { API_BASE_URL } from '../config'; // Assuming API_BASE_URL is defined here
import { SystemConfig, User, ApiKeyInfo } from '../types'; // Assuming these types are defined
import { useAuth } from '../contexts/AuthContext';
import DataCard from '../components/ui/DataCard'; // Added import for DataCard

const Settings: React.FC = () => {
  const { token, user } = useAuth();
  const [systemConfig, setSystemConfig] = useState<SystemConfig | null>(null);
  const [apiKeys, setApiKeys] = useState<ApiKeyInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchSettings = async () => {
      if (!token) {
        setError('Authentication token not found.');
        setLoading(false);
        return;
      }

      try {
        const headers = {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        };

        // Fetch System Config
        const configResponse = await fetch(`${API_BASE_URL}/admin/config`, { headers });
        if (!configResponse.ok) {
          const errorData = await configResponse.json();
          throw new Error(errorData.detail || 'Failed to fetch system config');
        }
        const configData: SystemConfig = await configResponse.json();
        setSystemConfig(configData);

        // Fetch API Keys
        const apiKeysResponse = await fetch(`${API_BASE_URL}/admin/api_keys`, { headers });
        if (!apiKeysResponse.ok) {
          const errorData = await apiKeysResponse.json();
          throw new Error(errorData.detail || 'Failed to fetch API keys');
        }
        const apiKeysData: ApiKeyInfo[] = await apiKeysResponse.json();
        setApiKeys(apiKeysData);

      } catch (err: any) {
        setError(err.message);
        console.error('Error fetching settings:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchSettings();
  }, [token]);

  const handleConfigChange = (key: keyof SystemConfig, value: any) => {
    setSystemConfig(prev => prev ? { ...prev, [key]: value } : null);
  };

  const handleUpdateConfig = async () => {
    if (!systemConfig || !token) return;

    try {
      const headers = {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      };
      const response = await fetch(`${API_BASE_URL}/admin/config`, {
        method: 'PUT',
        headers,
        body: JSON.stringify(systemConfig),
      });
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || `Failed to update system config`);
      }
      alert('Configuration updated successfully!');
    } catch (err: any) {
      setError(err.message);
      alert(`Error updating config: ${err.message}`);
      console.error('Error updating config:', err);
    }
  };

  const handleApiKeyUpdate = async (apiName: string, newKey: string) => {
    if (!token) return;

    try {
      const headers = {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      };
      const response = await fetch(`${API_BASE_URL}/admin/api_keys/${apiName}/update`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ new_key: newKey }),
      });
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || `Failed to update API key for ${apiName}`);
      }
      alert(`API key for ${apiName} updated successfully.`);
      // Refresh API keys after update
      const apiKeysResponse = await fetch(`${API_BASE_URL}/admin/api_keys`, { headers });
      const apiKeysData: ApiKeyInfo[] = await apiKeysResponse.json();
      setApiKeys(apiKeysData);

    } catch (err: any) {
      setError(err.message);
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
            <button
              onClick={handleUpdateConfig}
              className="bg-blue-500 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded focus:outline-none focus:shadow-outline"
            >
              Update Configuration
            </button>
          </div>
        ) : (
          <p className="text-nasa-light-gray">No general configuration available.</p>
        )}
      </DataCard>

      {/* User Management */}
      <DataCard title="User Management">
        <div className="max-h-96 overflow-y-auto pr-2">
          {/* Users data is not fetched in this component, so this section will be empty */}
          <p className="text-nasa-light-gray text-sm">User management functionality is typically handled in a dedicated component or page.</p>
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
                  <th className="py-2 px-4">Key (Masked)</th>
                  <th className="py-2 px-4">Enabled</th>
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
          {/* Audit logs data is not fetched in this component, so this section will be empty */}
          <p className="text-nasa-light-gray text-sm">Audit logs functionality is typically handled in a dedicated component or page.</p>
        </div>
      </DataCard>
    </div>
  );
};

export default Settings;
