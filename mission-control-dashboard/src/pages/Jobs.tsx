import React from 'react';
import useMissionControlStore from '../stores/missionControlStore';
import DataCard from '../components/ui/DataCard';
import { API_BASE_URL } from '../config'; // Assuming you have a config file for API_BASE_URL
import { useAuth } from '../hooks/useAuth'; // Import useAuth

const Jobs: React.FC = () => {
  const { data, fetchData } = useMissionControlStore(); // Get fetchData to refresh data
  const { token } = useAuth(); // Get token from useAuth

  if (!data) {
    return (
      <div className="text-center text-nasa-light-gray text-xl mt-20">
        <p>Awaiting data streams from Mission Control...</p>
        <p className="text-sm mt-2">Ensure backend services are running and WebSocket is connected.</p>
      </div>
    );
  }

  const { crawler_mission_status, satellite_fleet_status } = data;

  const handleJobAction = async (jobId: string, action: 'cancel') => {
    if (!window.confirm(`Are you sure you want to ${action} job ${jobId}?`)) {
      return;
    }
    try {
      if (!token) throw new Error("Authentication token not found.");
      const response = await fetch(`${API_BASE_URL}/api/monitoring/jobs/${jobId}/${action}`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || `Failed to ${action} job`);
      }
      alert(`Job ${jobId} ${action}led successfully.`);
      fetchData(); // Refresh data after action
    } catch (error: any) {
      alert(`Error ${action}ing job: ${error.message}`);
      console.error(`Error ${action}ing job ${jobId}:`, error);
    }
  };

  const handleGlobalJobAction = async (action: 'pause_all' | 'resume_all') => {
    if (!window.confirm(`Are you sure you want to ${action.replace('_', ' ')} jobs?`)) {
      return;
    }
    try {
      if (!token) throw new Error("Authentication token not found.");
      const response = await fetch(`${API_BASE_URL}/api/monitoring/jobs/${action}`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || `Failed to ${action.replace('_', ' ')} jobs`);
      }
      alert(`Jobs ${action.replace('_', ' ')} successfully.`);
      fetchData();
    } catch (error: any) {
      alert(`Error ${action.replace('_', ' ')} jobs: ${error.message}`);
      console.error(`Error ${action.replace('_', ' ')} jobs:`, error);
    }
  };

  const handleSatelliteControl = async (satelliteId: string, command: 'PAUSE' | 'RESUME' | 'SHUTDOWN' | 'RESTART') => {
    if (!window.confirm(`Are you sure you want to ${command.toLowerCase()} satellite ${satelliteId}?`)) {
      return;
    }
    try {
      if (!token) throw new Error("Authentication token not found.");
      const response = await fetch(`${API_BASE_URL}/api/monitoring/satellites/control/${satelliteId}/${command}`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || `Failed to ${command.toLowerCase()} satellite`);
      }
      alert(`Satellite ${satelliteId} ${command.toLowerCase()}ed successfully.`);
      fetchData();
    } catch (error: any) {
      alert(`Error ${command.toLowerCase()}ing satellite: ${error.message}`);
      console.error(`Error ${command.toLowerCase()}ing satellite ${satelliteId}:`, error);
    }
  };

  const handleGlobalSatelliteControl = async (command: 'PAUSE' | 'RESUME' | 'SHUTDOWN' | 'RESTART') => {
    if (!window.confirm(`Are you sure you want to ${command.toLowerCase()} ALL satellites?`)) {
      return;
    }
    try {
      if (!token) throw new Error("Authentication token not found.");
      const response = await fetch(`${API_BASE_URL}/api/monitoring/satellites/control/all/${command}`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || `Failed to ${command.toLowerCase()} all satellites`);
      }
      alert(`All satellites ${command.toLowerCase()}ed successfully.`);
      fetchData();
    } catch (error: any) {
      alert(`Error ${command.toLowerCase()}ing all satellites: ${error.message}`);
      console.error(`Error ${command.toLowerCase()}ing all satellites:`, error);
    }
  };

  return (
    <div className="space-y-8">
      <h1 className="text-4xl font-bold text-nasa-cyan mb-4">Job Management Console</h1>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <DataCard title="Active & Queued Jobs">
          <div className="space-y-4">
            <p className="text-nasa-light-gray text-lg">Active Jobs: <span className="text-nasa-amber">{crawler_mission_status.active_jobs_count}</span></p>
            <p className="text-nasa-light-gray text-lg">Queued Jobs: <span className="text-nasa-cyan">{crawler_mission_status.queued_jobs_count}</span></p>
            <p className="text-nasa-light-gray text-lg">Total Queue Depth: <span className="text-nasa-cyan">{crawler_mission_status.queue_depth}</span></p>
            <div className="flex space-x-2 mt-4">
              <button className="btn-primary" onClick={() => handleGlobalJobAction('pause_all')}>Pause All Jobs</button>
              <button className="btn-secondary" onClick={() => handleGlobalJobAction('resume_all')}>Resume All Jobs</button>
            </div>
          </div>
        </DataCard>

        <DataCard title="Recent Job Activity (24h)">
          <div className="space-y-4">
            <p className="text-nasa-light-gray text-lg">Completed Jobs: <span className="text-green-500">{crawler_mission_status.completed_jobs_24h_count}</span></p>
            <p className="text-nasa-light-gray text-lg">Failed Jobs: <span className="text-red-500">{crawler_mission_status.failed_jobs_24h_count}</span></p>
            <p className="text-nasa-light-gray text-lg">Total Pages Crawled: <span className="text-nasa-cyan">{crawler_mission_status.total_pages_crawled_24h}</span></p>
            <p className="text-nasa-light-gray text-lg">Avg. Job Completion Time: <span className="text-nasa-amber">{crawler_mission_status.avg_job_completion_time_seconds.toFixed(1)}s</span></p>
          </div>
        </DataCard>
      </div>

      <DataCard title="Satellite Job Status">
        <div className="flex space-x-2 mb-4">
          <button className="btn-primary" onClick={() => handleGlobalSatelliteControl('PAUSE')}>Pause All Satellites</button>
          <button className="btn-secondary" onClick={() => handleGlobalSatelliteControl('RESUME')}>Resume All Satellites</button>
          <button className="btn-danger" onClick={() => handleGlobalSatelliteControl('SHUTDOWN')}>Shutdown All Satellites</button>
        </div>
        <div className="max-h-96 overflow-y-auto pr-2">
          {satellite_fleet_status.length > 0 ? (
            <table className="w-full text-left text-nasa-light-gray text-sm">
              <thead>
                <tr className="text-nasa-cyan border-b border-nasa-light-gray">
                  <th className="py-2 px-4">Satellite ID</th>
                  <th className="py-2 px-4">Status</th>
                  <th className="py-2 px-4">Current Job</th>
                  <th className="py-2 px-4">Progress</th>
                  <th className="py-2 px-4">Jobs (24h)</th>
                  <th className="py-2 px-4">Errors (24h)</th>
                  <th className="py-2 px-4">Last Heartbeat</th>
                  <th className="py-2 px-4">Actions</th>
                </tr>
              </thead>
              <tbody>
                {satellite_fleet_status.map((sat) => (
                  <tr key={sat.satellite_id} className="border-b border-gray-700">
                    <td className="py-2 px-4">{sat.satellite_id}</td>
                    <td className={`py-2 px-4 ${
                      sat.status === 'active' ? 'text-green-500' :
                      sat.status === 'idle' ? 'text-nasa-amber' :
                      'text-red-500'
                    }`}>
                      {sat.status.toUpperCase()}
                    </td>
                    <td className="py-2 px-4">{sat.current_job_id ? `${sat.current_job_type || 'N/A'} (${sat.current_job_id.substring(0, 6)}...)` : 'Idle'}</td>
                    <td className="py-2 px-4">
                      {sat.current_job_progress !== null ? `${sat.current_job_progress.toFixed(1)}%` : 'N/A'}
                    </td>
                    <td className="py-2 px-4">{sat.jobs_completed_24h}</td>
                    <td className="py-2 px-4">{sat.errors_24h}</td>
                    <td className="py-2 px-4">{new Date(sat.last_heartbeat).toLocaleTimeString()}</td>
                    <td className="py-2 px-4 space-x-1">
                      <button className="btn-xs btn-secondary" onClick={() => handleSatelliteControl(sat.satellite_id, 'PAUSE')}>Pause</button>
                      <button className="btn-xs btn-primary" onClick={() => handleSatelliteControl(sat.satellite_id, 'RESUME')}>Resume</button>
                      <button className="btn-xs btn-danger" onClick={() => handleSatelliteControl(sat.satellite_id, 'SHUTDOWN')}>Shutdown</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="text-nasa-light-gray text-sm">No detailed satellite job data available.</p>
          )}
        </div>
      </DataCard>

      <DataCard title="Recent Job Errors (Last 24h)">
        <div className="max-h-60 overflow-y-auto pr-2">
          {crawler_mission_status.recent_job_errors.length > 0 ? (
            crawler_mission_status.recent_job_errors.map((error, index) => (
              <div key={index} className="text-sm text-red-400 mb-2 p-2 border border-red-600 rounded">
                <p><strong>Type:</strong> {error.error_type}</p>
                <p><strong>Message:</strong> {error.message}</p>
                <p><strong>URL:</strong> {error.url}</p>
                <p className="text-xs text-nasa-light-gray">Timestamp: {new Date(error.timestamp).toLocaleString()}</p>
                {error.details && (
                  <details className="text-xs text-nasa-light-gray mt-1">
                    <summary>Details</summary>
                    <pre className="overflow-x-auto text-xs bg-gray-800 p-1 rounded mt-1">
                      {JSON.stringify(error.details, null, 2)}
                    </pre>
                  </details>
                )}
              </div>
            ))
          ) : (
            <p className="text-nasa-light-gray text-sm">No recent job errors to display.</p>
          )}
        </div>
      </DataCard>

      {/* Placeholder for All Jobs Table - This would require fetching all jobs from /api/monitoring/jobs */}
      <DataCard title="All Crawl Jobs">
        <p className="text-nasa-light-gray text-sm">
          This section will display a comprehensive list of all crawl jobs with filtering and sorting options.
          (Functionality to be implemented by fetching data from <code>/api/monitoring/jobs</code>)
        </p>
        {/* Example:
        <table className="w-full text-left text-nasa-light-gray text-sm">
          <thead>
            <tr>
              <th>Job ID</th>
              <th>Target URL</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {allJobs.map(job => (
              <tr key={job.id}>
                <td>{job.id}</td>
                <td>{job.target_url}</td>
                <td>{job.status}</td>
                <td>
                  <button className="btn-xs btn-danger" onClick={() => handleJobAction(job.id, 'cancel')}>Cancel</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        */}
      </DataCard>
    </div>
  );
};

export default Jobs;
