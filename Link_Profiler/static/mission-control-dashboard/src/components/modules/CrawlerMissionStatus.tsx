import React from 'react';
import ModuleContainer from '../shared/ModuleContainer';
import MetricDisplay from '../shared/MetricDisplay';
import ListDisplay from '../shared/ListDisplay';
import ChartContainer from '../shared/ChartContainer'; // New import
import LineChart from '../charts/LineChart'; // New import
import { CrawlError, SatelliteFleetStatus } from '../../types'; // Import specific types

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
    satellite_utilization_percentage: number | null; // Updated type
    avg_job_completion_time_seconds: number | null; // Updated type
    recent_job_errors: CrawlError[]; // Updated type
  };
  satelliteFleet: SatelliteFleetStatus[]; // Updated type
}

const CrawlerMissionStatus: React.FC<CrawlerMissionStatusProps> = ({ status, satelliteFleet }) => {
  // Removed dummy data for chart demonstration as historical data is not yet available from backend.
  // The LineChart component is also removed from the JSX for now.

  return (
    <ModuleContainer title="Crawler Mission Status">
      <div className="grid grid-cols-2 gap-4 text-lg">
        <MetricDisplay label="Active Jobs" value={status.active_jobs_count} valueColorClass="text-nasa-amber" />
        <MetricDisplay label="Queued Jobs" value={status.queued_jobs_count} valueColorClass="text-nasa-cyan" />
        <MetricDisplay label="Queue Depth" value={status.queue_depth} valueColorClass="text-nasa-cyan" />
        <MetricDisplay label="Active Satellites" value={`${status.active_satellites_count}/${status.total_satellites_count}`} valueColorClass="text-nasa-amber" />
        <div className="col-span-2">
          <MetricDisplay label="Satellite Utilization" value={(status.satellite_utilization_percentage ?? 0).toFixed(1)} unit="%" valueColorClass="text-nasa-cyan" />
        </div>
        <div className="col-span-2">
          <MetricDisplay label="Completed (24h)" value={status.completed_jobs_24h_count} valueColorClass="text-nasa-green" />
        </div>
        <div className="col-span-2">
          <MetricDisplay label="Failed (24h)" value={status.failed_jobs_24h_count} valueColorClass="text-nasa-red" />
        </div>
      </div>

      <ListDisplay
        title="Satellite Fleet"
        items={satelliteFleet.map(sat => `${sat.satellite_id} - ${sat.status.toUpperCase()} (${new Date(sat.last_heartbeat).toLocaleTimeString()})`)}
        emptyMessage="No satellite data available."
        maxHeight="max-h-40"
        itemColorClass={(item: string) => { // Explicitly type item
          if (item.includes('UNRESPONSIVE')) return 'text-nasa-red';
          if (item.includes('IDLE')) return 'text-nasa-amber';
          return 'text-nasa-green';
        }}
      />

      <ListDisplay
        title="Recent Job Errors"
        items={status.recent_job_errors.map(err => `${err.error_type}: ${err.message} (URL: ${err.url})`)}
        emptyMessage="No recent job errors."
        itemColorClass="text-nasa-red" // Errors are red
        maxHeight="max-h-40"
      />

      {/* Chart removed as historical data is not yet available from backend */}
      {/*
      <ChartContainer title="Job Completion (24h)">
        <LineChart
          data={jobCompletionData}
          dataKey="name"
          lineKeys={[
            { key: 'completed', stroke: '#22c55e', name: 'Completed' },
            { key: 'failed', stroke: '#ef4444', name: 'Failed' },
          ]}
        />
      </ChartContainer>
      */}
    </ModuleContainer>
  );
};

export default CrawlerMissionStatus;
