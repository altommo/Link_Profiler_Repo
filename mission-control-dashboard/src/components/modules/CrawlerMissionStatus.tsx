import React from 'react';

interface CrawlerMissionStatusProps {
  status: {
    active_jobs_count: number;
    queued_jobs_count: number;
    completed_jobs_24h_count: number;
    failed_jobs_24h_count: number;
    total_pages_crawled_24h: number;
    queue_depth: number;
    active_satellites_count: number;
    total_satellites_count: number;
    satellite_utilization_percentage: number;
    avg_job_completion_time_seconds: number;
    recent_job_errors: any[];
  };
  satelliteFleet: {
    satellite_id: string;
    status: string;
    last_heartbeat: string;
    jobs_completed_24h: number;
    errors_24h: number;
    avg_job_duration_seconds: number | null;
    current_job_id: string | null;
    current_job_type: string | null;
    current_job_progress: number | null;
  }[];
}

const CrawlerMissionStatus: React.FC<CrawlerMissionStatusProps> = ({ status, satelliteFleet }) => {
  return (
    <div className="bg-nasa-gray p-6 rounded-lg shadow-lg border border-nasa-cyan">
      <h2 className="text-2xl font-bold text-nasa-cyan mb-4">Crawler Mission Status</h2>
      <div className="grid grid-cols-2 gap-4 text-lg">
        <div>
          <p className="text-nasa-light-gray">Active Jobs:</p>
          <p className="text-nasa-amber text-3xl">{status.active_jobs_count}</p>
        </div>
        <div>
          <p className="text-nasa-light-gray">Queued Jobs:</p>
          <p className="text-nasa-cyan text-3xl">{status.queued_jobs_count}</p>
        </div>
        <div>
          <p className="text-nasa-light-gray">Queue Depth:</p>
          <p className="text-nasa-cyan text-3xl">{status.queue_depth}</p>
        </div>
        <div>
          <p className="text-nasa-light-gray">Active Satellites:</p>
          <p className="text-nasa-amber text-3xl">{status.active_satellites_count}/{status.total_satellites_count}</p>
        </div>
        <div className="col-span-2">
          <p className="text-nasa-light-gray">Satellite Utilization:</p>
          <p className="text-nasa-cyan text-3xl">{status.satellite_utilization_percentage}%</p>
        </div>
        <div className="col-span-2">
          <p className="text-nasa-light-gray">Completed (24h):</p>
          <p className="text-nasa-cyan text-3xl">{status.completed_jobs_24h_count}</p>
        </div>
        <div className="col-span-2">
          <p className="text-nasa-light-gray">Failed (24h):</p>
          <p className="text-red-500 text-3xl">{status.failed_jobs_24h_count}</p>
        </div>
      </div>

      <h3 className="text-xl font-bold text-nasa-cyan mt-6 mb-3">Satellite Fleet</h3>
      <div className="max-h-40 overflow-y-auto pr-2">
        {satelliteFleet.length > 0 ? (
          satelliteFleet.map((sat) => (
            <div key={sat.satellite_id} className="flex justify-between items-center text-sm mb-1">
              <span className="text-nasa-light-gray">{sat.satellite_id}</span>
              <span className={
                sat.status === 'active' ? 'text-green-500' :
                sat.status === 'idle' ? 'text-nasa-amber' :
                'text-red-500'
              }>
                {sat.status.toUpperCase()}
              </span>
              <span className="text-nasa-light-gray text-xs">
                {new Date(sat.last_heartbeat).toLocaleTimeString()}
              </span>
            </div>
          ))
        ) : (
          <p className="text-nasa-light-gray text-sm">No satellite data available.</p>
        )}
      </div>

      <h3 className="text-xl font-bold text-nasa-cyan mt-6 mb-3">Recent Job Errors</h3>
      <div className="max-h-40 overflow-y-auto pr-2">
        {status.recent_job_errors.length > 0 ? (
          status.recent_job_errors.map((error, index) => (
            <div key={index} className="text-sm text-red-400 mb-1">
              <p><strong>{error.error_type}</strong>: {error.message}</p>
              <p className="text-xs text-red-500 ml-2">URL: {error.url}</p>
            </div>
          ))
        ) : (
          <p className="text-nasa-light-gray text-sm">No recent job errors.</p>
        )}
      </div>
    </div>
  );
};

export default CrawlerMissionStatus;
