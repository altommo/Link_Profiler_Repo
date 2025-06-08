import React, { useEffect, useState } from 'react';
import ModuleContainer from '../components/shared/ModuleContainer';
import MetricDisplay from '../components/shared/MetricDisplay';
import ListDisplay from '../components/shared/ListDisplay';
import ApiQuotaStatus from '../components/modules/ApiQuotaStatus';
import BacklinkDiscovery from '../components/modules/BacklinkDiscovery';
import PerformanceOptimization from '../components/modules/PerformanceOptimization';
import useWebSocket from '../hooks/useWebSocket'; // Corrected import
import {
  DashboardRealtimeUpdates,
  CrawlerMissionStatus,
  BacklinkDiscoveryMetrics,
  ApiQuotaStatus as ApiQuotaStatusType, // Alias to avoid conflict if needed
  DomainIntelligenceMetrics,
  PerformanceOptimizationMetrics,
  DashboardAlert,
  SatelliteFleetStatus,
} from '../types'; // Import all necessary types

const Overview: React.FC = () => {
  const [dashboardData, setDashboardData] = useState<DashboardRealtimeUpdates | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleWebSocketMessage = (data: DashboardRealtimeUpdates) => {
    setDashboardData(data);
    setError(null);
  };

  const handleWebSocketError = (event: Event) => {
    console.error('WebSocket error:', event);
    setError('WebSocket connection error. Data might be outdated.');
  };

  const { isConnected } = useWebSocket({
    path: '/ws/dashboard',
    onMessage: handleWebSocketMessage,
    onError: handleWebSocketError,
  });

  if (error) {
    return <div className="text-red-500 p-4">{error}</div>;
  }

  if (!dashboardData) {
    return <div className="text-white p-4">Loading dashboard data...</div>;
  }

  const {
    crawler_mission_status,
    backlink_discovery_metrics,
    api_quota_statuses,
    domain_intelligence_metrics,
    performance_optimization_metrics,
    alerts,
    satellite_fleet_status,
  } = dashboardData;

  return (
    <div className="p-6 bg-gray-900 min-h-screen text-white">
      <h1 className="text-3xl font-bold mb-6">Mission Control Overview</h1>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
        {/* Crawler Mission Status */}
        <ModuleContainer title="Crawler Mission Status">
          <div className="grid grid-cols-2 gap-4">
            <MetricDisplay label="Active Jobs" value={crawler_mission_status.active_jobs_count} />
            <MetricDisplay label="Queued Jobs" value={crawler_mission_status.queued_jobs_count} />
            <MetricDisplay label="Completed (24h)" value={crawler_mission_status.completed_jobs_24h_count} />
            <MetricDisplay label="Failed (24h)" value={crawler_mission_status.failed_jobs_24h_count} />
            <MetricDisplay label="Pages Crawled (24h)" value={crawler_mission_status.total_pages_crawled_24h} />
            <MetricDisplay label="Queue Depth" value={crawler_mission_status.queue_depth} />
            <MetricDisplay label="Active Satellites" value={`${crawler_mission_status.active_satellites_count}/${crawler_mission_status.total_satellites_count}`} />
            <MetricDisplay label="Satellite Utilization" value={`${crawler_mission_status.satellite_utilization_percentage.toFixed(1)}%`} />
            <MetricDisplay label="Avg. Job Completion" value={`${crawler_mission_status.avg_job_completion_time_seconds.toFixed(1)}s`} />
          </div>
          {crawler_mission_status.recent_job_errors && crawler_mission_status.recent_job_errors.length > 0 && (
            <ListDisplay
              title="Recent Job Errors"
              items={crawler_mission_status.recent_job_errors.map(err => `${err.error_type}: ${err.message.substring(0, 50)}...`)}
              emptyMessage="No recent job errors."
              itemColorClass={(item: string) => { // Explicitly type item
                if (item.includes('[CRITICAL]')) return 'text-red-500';
                if (item.includes('[WARNING]')) return 'text-orange-400';
                return 'text-blue-400';
              }}
              maxHeight="max-h-32"
            />
          )}
        </ModuleContainer>

        {/* API Quota & Performance */}
        <ApiQuotaStatus statuses={api_quota_statuses} />

        {/* Alerts & Notifications */}
        <ModuleContainer title="Alerts & Notifications">
          {alerts.length > 0 ? (
            <ListDisplay
              title="Active Alerts"
              items={alerts.map(alert => `[${alert.severity}] ${alert.message}`)}
              emptyMessage="No active alerts."
              itemColorClass={(item: string) => { // Explicitly type item
                if (item.includes('[CRITICAL]')) return 'text-red-500';
                if (item.includes('[WARNING]')) return 'text-orange-400';
                return 'text-blue-400';
              }}
              maxHeight="max-h-64"
            />
          ) : (
            <p className="text-gray-400">No active alerts.</p>
          )}
        </ModuleContainer>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        {/* Backlink Discovery Operations */}
        <BacklinkDiscovery metrics={backlink_discovery_metrics} />

        {/* Domain Intelligence Command Center */}
        <ModuleContainer title="Domain Intelligence Command Center">
          <div className="grid grid-cols-2 gap-4">
            <MetricDisplay label="Total Domains Analyzed" value={domain_intelligence_metrics.total_domains_analyzed} />
            <MetricDisplay label="Valuable Expired Domains Found" value={domain_intelligence_metrics.valuable_expired_domains_found} />
            <MetricDisplay label="Avg. Domain Value Score" value={domain_intelligence_metrics.avg_domain_value_score.toFixed(1)} />
            <MetricDisplay label="New Domains Added (24h)" value={domain_intelligence_metrics.new_domains_added_24h} />
          </div>
          <ListDisplay
            title="Top Niches Identified"
            items={domain_intelligence_metrics.top_niches_identified}
            emptyMessage="No niches identified."
          />
        </ModuleContainer>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Performance Optimization Center */}
        <PerformanceOptimization metrics={performance_optimization_metrics} />

        {/* Satellite Fleet Status */}
        <ModuleContainer title="Satellite Fleet Status">
          {satellite_fleet_status.length > 0 ? (
            <ListDisplay
              title="Satellites"
              items={satellite_fleet_status.map(sat => `${sat.satellite_id} - ${sat.status} (Last Seen: ${new Date(sat.last_heartbeat).toLocaleTimeString()})`)}
              emptyMessage="No satellites online."
              itemColorClass={(item: string) => { // Explicitly type item
                if (item.includes('unresponsive')) return 'text-red-500';
                if (item.includes('idle')) return 'text-orange-400';
                return 'text-green-400';
              }}
              maxHeight="max-h-64"
            />
          ) : (
            <p className="text-gray-400">No satellites online.</p>
          )}
        </ModuleContainer>
      </div>
    </div>
  );
};

export default Overview;
