import React from 'react';
import useMissionControlStore from '../stores/missionControlStore';
import ModuleContainer from '../components/shared/ModuleContainer';
import MetricDisplay from '../components/shared/MetricDisplay';
import ListDisplay from '../components/shared/ListDisplay';

// Re-import existing modules
import CrawlerMissionStatus from '../components/modules/CrawlerMissionStatus';
import BacklinkDiscovery from '../components/modules/BacklinkDiscovery';
import ApiQuotaStatus from '../components/modules/ApiQuotaStatus';
import DomainIntelligence from '../components/modules/DomainIntelligence';
import PerformanceOptimization from '../components/modules/PerformanceOptimization';
import AlertsDisplay from '../components/modules/AlertsDisplay';

const Overview: React.FC = () => {
  const { data } = useMissionControlStore();

  if (!data) {
    return (
      <div className="text-center text-nasa-light-gray text-xl mt-20">
        <p>Awaiting data streams from Mission Control...</p>
        <p className="text-sm mt-2">Ensure backend services are running and WebSocket is connected.</p>
      </div>
    );
  }

  // Destructure data for easier access
  const {
    crawler_mission_status,
    backlink_discovery_metrics,
    api_quota_statuses,
    domain_intelligence_metrics,
    performance_optimization_metrics,
    alerts,
    satellite_fleet_status,
  } = data;

  return (
    <div className="space-y-8">
      <h1 className="text-4xl font-bold text-nasa-cyan mb-4">Mission Overview</h1>
      <p className="text-sm text-nasa-light-gray">Last Updated: {new Date(data.timestamp).toLocaleTimeString()}</p>

      {/* Adjusted grid for responsiveness: 1 column on small, 2 on medium, 3 on large */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {/* Crawler Mission Status - Updated to use new shared components */}
        <CrawlerMissionStatus
          status={crawler_mission_status}
          satelliteFleet={satellite_fleet_status}
        />

        {/* Backlink Discovery Operations - Updated to use new shared components */}
        <BacklinkDiscovery
          metrics={backlink_discovery_metrics}
        />

        {/* API Quota Management - Still uses its own internal rendering for progress bars */}
        <ApiQuotaStatus
          statuses={api_quota_statuses}
        />

        {/* Domain Intelligence Command Center - Updated to use new shared components */}
        <DomainIntelligence
          metrics={domain_intelligence_metrics}
        />

        {/* Performance Optimization Center - Updated to use new shared components */}
        <PerformanceOptimization
          metrics={performance_optimization_metrics}
        />

        {/* System Alerts - Still uses its own internal rendering for alert details */}
        <AlertsDisplay
          alerts={alerts}
        />
      </div>
    </div>
  );
};

export default Overview;
