import React, { useState, useEffect } from 'react';
import { API_BASE_URL } from '../config';
import DataCard from '../components/ui/DataCard';
import ModuleContainer from '../components/shared/ModuleContainer';
import MetricDisplay from '../components/shared/MetricDisplay';
import ListDisplay from '../components/shared/ListDisplay';
import { CrawlJob } from '../types'; // Import CrawlJob type
import useMissionControlStore from '../stores/missionControlStore'; // Import the store

const Jobs: React.FC = () => {
  const [jobs, setJobs] = useState<CrawlJob[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  
  // Get satelliteFleetStatus from the central store
  const satelliteFleetStatus = useMissionControlStore((state) => state.data?.satellite_fleet_status || []);

  const fetchJobs = async () => {
    try {
      const token = localStorage.getItem('token');
      const headers = {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      };
      const response = await fetch(`${API_BASE_URL}/api/monitoring/jobs`, { headers });
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to fetch jobs');
      }
      const data: CrawlJob[] = await response.json();
      setJobs(data);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // Removed fetchSatelliteStatus as it's now sourced from the store

  useEffect(() => {
    fetchJobs();
    const interval = setInterval(() => {
      fetchJobs();
    }, 5000); // Refresh jobs every 5 seconds
    return () => clearInterval(interval);
  }, []);

  const handleControlAction = async (endpoint: string, actionDescription: string, payload?: any) => {
    try {
      const token = localStorage.getItem('token');
      const headers = {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      };
      const response = await fetch(`${API_BASE_URL}/api/monitoring/${endpoint}`, {
        method: 'POST',
        headers,
        body: payload ? JSON.stringify(payload) : undefined,
      });
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || `Failed to ${actionDescription.toLowerCase()}`);
      }
      alert(`${actionDescription} successful!`);
      fetchJobs(); // Refresh jobs after action
      // No need to fetchSatelliteStatus here, as the store will update it via WebSocket
    } catch (err: any) {
      setError(err.message);
      alert(`Error: ${err.message}`);
    }
  };

  if (loading) return <div className="p-6 text-nasa-light-gray">Loading jobs...</div>;
  if (error) return <div className="p-6 text-nasa-red">Error: {error}</div>;

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'COMPLETED': return 'text-nasa-green';
      case 'IN_PROGRESS': return 'text-nasa-blue';
      case 'FAILED': return 'text-nasa-red';
      case 'QUEUED': return 'text-nasa-amber';
      case 'PENDING': return 'text-nasa-light-gray';
      case 'CANCELLED': return 'text-purple-500'; // Keep purple for now, not in NASA palette
      case 'active': return 'text-nasa-green'; // For satellite status
      case 'idle': return 'text-nasa-amber'; // For satellite status
      case 'unresponsive': return 'text-nasa-red'; // For satellite status
      default: return 'text-nasa-light-gray';
    }
  };

  return (
    <div className="p-6 bg-nasa-dark-blue min-h-screen text-nasa-light-gray">
      <h1 className="text-3xl font-bold mb-6">Job Management</h1>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-6">
        <DataCard title="Global Controls">
          <button
            onClick={() => handleControlAction('jobs/pause_all', 'Pause All Jobs')}
            className="bg-nasa-amber hover:bg-orange-700 text-white font-bold py-2 px-4 rounded mr-2 mb-2"
          >
            Pause All Jobs
          </button>
          <button
            onClick={() => handleControlAction('jobs/resume_all', 'Resume All Jobs')}
            className="bg-nasa-green hover:bg-green-700 text-white font-bold py-2 px-4 rounded mb-2"
          >
            Resume All Jobs
          </button>
          <button
            onClick={() => handleControlAction('satellites/control/all/SHUTDOWN', 'Shutdown All Satellites')}
            className="bg-nasa-red hover:bg-red-700 text-white font-bold py-2 px-4 rounded mb-2"
          >
            Shutdown All Satellites
          </button>
        </DataCard>

        <ModuleContainer title="Satellite Fleet Status">
          <div className="overflow-x-auto">
            <table className="min-w-full bg-nasa-medium-blue rounded-lg">
              <thead>
                <tr className="bg-nasa-dark-blue text-left text-nasa-light-gray uppercase text-sm leading-normal">
                  <th className="py-3 px-6">ID</th>
                  <th className="py-3 px-6">Status</th>
                  <th className="py-3 px-6">Last Seen</th>
                  <th className="py-3 px-6">Actions</th>
                </tr>
              </thead>
              <tbody className="text-nasa-light-gray text-sm font-light">
                {satelliteFleetStatus.map((sat) => ( // Use sat directly from store
                  <tr key={sat.satellite_id} className="border-b border-gray-700">
                    <td className="py-3 px-6 text-left whitespace-nowrap">{sat.satellite_id}</td>
                    <td className="py-3 px-6 text-left">
                      <span className={`font-semibold ${getStatusColor(sat.status)}`}>
                        {sat.status}
                      </span>
                    </td>
                    <td className="py-3 px-6 text-left">{new Date(sat.last_heartbeat).toLocaleString()}</td>
                    <td className="py-3 px-6 text-left">
                      <button
                        onClick={() => handleControlAction(`satellites/control/${sat.satellite_id}/PAUSE`, `Pause ${sat.satellite_id}`)}
                        className="bg-nasa-blue hover:bg-blue-700 text-white py-1 px-2 rounded text-xs mr-1"
                      >
                        Pause
                      </button>
                      <button
                        onClick={() => handleControlAction(`satellites/control/${sat.satellite_id}/RESUME`, `Resume ${sat.satellite_id}`)}
                        className="bg-nasa-green hover:bg-green-700 text-white py-1 px-2 rounded text-xs mr-1"
                      >
                        Resume
                      </button>
                      <button
                        onClick={() => handleControlAction(`satellites/control/${sat.satellite_id}/SHUTDOWN`, `Shutdown ${sat.satellite_id}`)}
                        className="bg-nasa-red hover:bg-red-700 text-white py-1 px-2 rounded text-xs"
                      >
                        Shutdown
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </ModuleContainer>
      </div>

      <h2 className="text-2xl font-bold mb-4">All Jobs</h2>
      <div className="overflow-x-auto bg-nasa-medium-blue rounded-lg shadow-md">
        <table className="min-w-full leading-normal">
          <thead>
            <tr className="bg-nasa-dark-blue text-left text-nasa-light-gray uppercase text-sm leading-normal">
              <th className="py-3 px-6">Job ID</th>
              <th className="py-3 px-6">Target URL</th>
              <th className="py-3 px-6">Type</th>
              <th className="py-3 px-6">Status</th>
              <th className="py-3 px-6">Progress</th>
              <th className="py-3 px-6">Created</th>
              <th className="py-3 px-6">Actions</th>
            </tr>
          </thead>
          <tbody className="text-nasa-light-gray text-sm font-light">
            {jobs.map((job) => (
              <tr key={job.id} className="border-b border-gray-700 hover:bg-nasa-dark-blue">
                <td className="py-3 px-6 text-left whitespace-nowrap">{job.id}</td>
                <td className="py-3 px-6 text-left">{job.target_url}</td> {/* Corrected to target_url */}
                <td className="py-3 px-6 text-left">{job.job_type}</td>
                <td className="py-3 px-6 text-left">
                  <span className={`font-semibold ${getStatusColor(job.status)}`}>
                    {job.status}
                  </span>
                </td>
                <td className="py-3 px-6 text-left">{job.progress_percentage.toFixed(1)}%</td> {/* Corrected to progress_percentage */}
                <td className="py-3 px-6 text-left">{new Date(job.created_at).toLocaleString()}</td> {/* Corrected to created_at */}
                <td className="py-3 px-6 text-left">
                  <button
                    onClick={() => handleControlAction(`jobs/${job.id}/cancel`, `Cancel Job ${job.id}`)}
                    className="bg-nasa-red hover:bg-red-700 text-white py-1 px-2 rounded text-xs"
                  >
                    Cancel
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default Jobs;
