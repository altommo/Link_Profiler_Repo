import React from 'react';
import useMissionControlStore from '../stores/missionControlStore';
import ModuleContainer from '../components/shared/ModuleContainer'; // New import
import MetricDisplay from '../components/shared/MetricDisplay'; // New import
import ListDisplay from '../components/shared/ListDisplay'; // New import

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
    satellite_fleet_status, // Still needed for CrawlerMissionStatus
  } = data;

  return (
    <div className="space-y-8">
      <h1 className="text-4xl font-bold text-nasa-cyan mb-4">Mission Overview</h1>
      <p className="text-sm text-nasa-light-gray">Last Updated: {new Date(data.timestamp).toLocaleTimeString()}</p>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {/* Crawler Mission Status - Updated to use new shared components */}
        <ModuleContainer title="Crawler Mission Status">
          <div className="grid grid-cols-2 gap-4 text-lg">
            <MetricDisplay label="Active Jobs" value={crawler_mission_status.active_jobs_count} valueColorClass="text-nasa-amber" />
            <MetricDisplay label="Queued Jobs" value={crawler_mission_status.queued_jobs_count} valueColorClass="text-nasa-cyan" />
            <MetricDisplay label="Queue Depth" value={crawler_mission_status.queue_depth} valueColorClass="text-nasa-cyan" />
            <MetricDisplay label="Active Satellites" value={`${crawler_mission_status.active_satellites_count}/${crawler_mission_status.total_satellites_count}`} valueColorClass="text-nasa-amber" />
            <div className="col-span-2">
              <MetricDisplay label="Satellite Utilization" value={crawler_mission_status.satellite_utilization_percentage.toFixed(1)} unit="%" valueColorClass="text-nasa-cyan" />
            </div>
            <div className="col-span-2">
              <MetricDisplay label="Completed (24h)" value={crawler_mission_status.completed_jobs_24h_count} valueColorClass="text-nasa-cyan" />
            </div>
            <div className="col-span-2">
              <MetricDisplay label="Failed (24h)" value={crawler_mission_status.failed_jobs_24h_count} valueColorClass="text-red-500" />
            </div>
          </div>
          <ListDisplay
            title="Recent Job Errors"
            items={crawler_mission_status.recent_job_errors.map(err => `${err.error_type}: ${err.message} (URL: ${err.url})`)}
            emptyMessage="No recent job errors."
            itemColorClass="text-red-400"
            maxHeight="max-h-40"
          />
        </ModuleContainer>

        {/* Backlink Discovery Operations - Updated to use new shared components */}
        <ModuleContainer title="Backlink Discovery Operations">
          <div className="grid grid-cols-2 gap-4 text-lg">
            <MetricDisplay label="Total Backlinks" value={backlink_discovery_metrics.total_backlinks_discovered} valueColorClass="text-nasa-amber" />
            <MetricDisplay label="Unique Domains" value={backlink_discovery_metrics.unique_domains_discovered} valueColorClass="text-nasa-cyan" />
            <MetricDisplay label="New (24h)" value={backlink_discovery_metrics.new_backlinks_24h} valueColorClass="text-nasa-cyan" />
            <MetricDisplay label="Avg. Authority Score" value={backlink_discovery_metrics.avg_authority_score.toFixed(1)} valueColorClass="text-nasa-amber" />
            <div className="col-span-2">
              <MetricDisplay label="Potential Spam (24h)" value={backlink_discovery_metrics.potential_spam_links_24h} valueColorClass="text-red-500" />
            </div>
          </div>
          <ListDisplay
            title="Top Linking Domains"
            items={backlink_discovery_metrics.top_linking_domains}
            emptyMessage="No top linking domains yet."
            maxHeight="max-h-40"
          />
          <ListDisplay
            title="Top Target URLs"
            items={backlink_discovery_metrics.top_target_urls}
            emptyMessage="No top target URLs yet."
            maxHeight="max-h-40"
          />
        </ModuleContainer>

        {/* API Quota Management - Still uses its own internal rendering for progress bars */}
        <ApiQuotaStatus
          statuses={api_quota_statuses}
        />

        {/* Domain Intelligence Command Center - Updated to use new shared components */}
        <ModuleContainer title="Domain Intelligence Command Center">
          <div className="grid grid-cols-2 gap-4 text-lg">
            <MetricDisplay label="Total Analyzed" value={domain_intelligence_metrics.total_domains_analyzed} valueColorClass="text-nasa-amber" />
            <MetricDisplay label="Valuable Expired" value={domain_intelligence_metrics.valuable_expired_domains_found} valueColorClass="text-nasa-cyan" />
            <MetricDisplay label="Avg. Value Score" value={domain_intelligence_metrics.avg_domain_value_score.toFixed(1)} valueColorClass="text-nasa-amber" />
            <MetricDisplay label="New (24h)" value={domain_intelligence_metrics.new_domains_added_24h} valueColorClass="text-nasa-cyan" />
          </div>
          <ListDisplay
            title="Top Niches Identified"
            items={domain_intelligence_metrics.top_niches_identified}
            emptyMessage="No top niches identified yet."
            maxHeight="max-h-40"
          />
        </ModuleContainer>

        {/* Performance Optimization Center - Updated to use new shared components */}
        <ModuleContainer title="Performance Optimization Center">
          <div className="grid grid-cols-2 gap-4 text-lg">
            <MetricDisplay label="Avg. Crawl Speed" value={performance_optimization_metrics.avg_crawl_speed_pages_per_minute.toFixed(1)} unit="pages/min" valueColorClass="text-nasa-amber" />
            <MetricDisplay label="Avg. Success Rate" value={performance_optimization_metrics.avg_success_rate_percentage.toFixed(1)} unit="%" valueColorClass="text-nasa-cyan" />
            <MetricDisplay label="Avg. Response Time" value={performance_optimization_metrics.avg_response_time_ms.toFixed(0)} unit="ms" valueColorClass="text-nasa-amber" />
          </div>
          <ListDisplay
            title="Bottlenecks Detected"
            items={performance_optimization_metrics.bottlenecks_detected}
            emptyMessage="No bottlenecks detected."
            itemColorClass="text-red-400"
            maxHeight="max-h-24"
          />
          <ListDisplay
            title="Top Performing Satellites"
            items={performance_optimization_metrics.top_performing_satellites}
            emptyMessage="N/A"
            itemColorClass="text-green-400"
            maxHeight="max-h-24"
          />
          <ListDisplay
            title="Worst Performing Satellites"
            items={performance_optimization_metrics.worst_performing_satellites}
            emptyMessage="N/A"
            itemColorClass="text-red-400"
            maxHeight="max-h-24"
          />
        </ModuleContainer>

        {/* System Alerts - Still uses its own internal rendering for alert details */}
        <AlertsDisplay
          alerts={alerts}
        />
      </div>
    </div>
  );
};

export default Overview;
