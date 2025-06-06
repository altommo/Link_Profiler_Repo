import React from 'react';
import useMissionControlStore from '../stores/missionControlStore';
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

  return (
    <div className="space-y-8">
      <h1 className="text-4xl font-bold text-nasa-cyan mb-4">Mission Overview</h1>
      {/* Last Updated timestamp is now handled in App.tsx Layout */}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        <CrawlerMissionStatus
          status={data.crawler_mission_status}
          satelliteFleet={data.satellite_fleet_status}
        />
        <BacklinkDiscovery
          metrics={data.backlink_discovery_metrics}
        />
        <ApiQuotaStatus
          statuses={data.api_quota_statuses}
        />
        <DomainIntelligence
          metrics={data.domain_intelligence_metrics}
        />
        <PerformanceOptimization
          metrics={data.performance_optimization_metrics}
        />
        <AlertsDisplay
          alerts={data.alerts}
        />
      </div>
    </div>
  );
};

export default Overview;
