import React from 'react';
import useMissionControlStore from '../stores/missionControlStore';
import DataCard from '../components/ui/DataCard';

const Jobs: React.FC = () => {
  const { data } = useMissionControlStore();

  if (!data) {
    return (
      <div className="text-center text-nasa-light-gray text-xl mt-20">
        <p>Awaiting data streams from Mission Control...</p>
        <p className="text-sm mt-2">Ensure backend services are running and WebSocket is connected.</p>
      </div>
    );
  }

  const { crawler_mission_status, satellite_fleet_status } = data;

  return (
    <div className="space-y-8">
      <h1 className="text-4xl font-bold text-nasa-cyan mb-4">Job Management Console</h1>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <DataCard title="Active & Queued Jobs">
          <div className="space-y-4">
            <p className="text-nasa-light-gray text-lg">Active Jobs: <span className="text-nasa-amber">{crawler_mission_status.active_jobs_count}</span></p>
            <p className="text-nasa-light-gray text-lg">Queued Jobs: <span className="text-nasa-cyan">{crawler_mission_status.queued_jobs_count}</span></p>
            <p className="text-nasa-light-gray text-lg">Total Queue Depth: <span className="text-nasa-cyan">{crawler_mission_status.queue_depth}</span></p>
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
    </div>
  );
};

export default Jobs;
