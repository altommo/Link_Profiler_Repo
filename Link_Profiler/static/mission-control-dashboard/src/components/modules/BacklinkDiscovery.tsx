import React from 'react';
import ModuleContainer from '../shared/ModuleContainer';
import MetricDisplay from '../shared/MetricDisplay';
import ListDisplay from '../shared/ListDisplay';
import ChartContainer from '../shared/ChartContainer'; // New import
import LineChart from '../charts/LineChart'; // New import

interface BacklinkDiscoveryProps {
  metrics: {
    total_backlinks_discovered: number;
    unique_domains_discovered: number;
    new_backlinks_24h: number;
    avg_authority_score: number | null;
    top_linking_domains: string[] | null; // Changed to allow null
    top_target_urls: string[] | null; // Changed to allow null
    potential_spam_links_24h: number;
  };
}

const BacklinkDiscovery: React.FC<BacklinkDiscoveryProps> = ({ metrics }) => {
  // Removed dummy data for chart demonstration as historical data is not yet available from backend.
  // The LineChart component is also removed from the JSX for now.

  return (
    <ModuleContainer title="Backlink Discovery Operations">
      <div className="grid grid-cols-2 gap-4 text-lg">
        <MetricDisplay label="Total Backlinks" value={metrics.total_backlinks_discovered} valueColorClass="text-nasa-amber" />
        <MetricDisplay label="Unique Domains" value={metrics.unique_domains_discovered} valueColorClass="text-nasa-cyan" />
        <MetricDisplay label="New (24h)" value={metrics.new_backlinks_24h} valueColorClass="text-nasa-cyan" />
        <MetricDisplay label="Avg. Authority Score" value={(metrics.avg_authority_score ?? 0).toFixed(1)} valueColorClass="text-nasa-amber" />
        <div className="col-span-2">
          <MetricDisplay label="Potential Spam (24h)" value={metrics.potential_spam_links_24h} valueColorClass="text-red-500" />
        </div>
      </div>

      <ListDisplay
        title="Top Linking Domains"
        items={metrics.top_linking_domains ?? []} // Safely access
        emptyMessage="No top linking domains yet."
        maxHeight="max-h-40"
      />

      <ListDisplay
        title="Top Target URLs"
        items={metrics.top_target_urls ?? []} // Safely access
        emptyMessage="No top target URLs yet."
        maxHeight="max-h-40"
      />

      {/* Chart removed as historical data is not yet available from backend */}
      {/*
      <ChartContainer title="Discovery Rate (Last 7 Days)">
        <LineChart
          data={discoveryRateData}
          dataKey="name"
          lineKeys={[
            { key: 'discovered', stroke: '#00FFFF', name: 'Discovered' },
            { key: 'spam', stroke: '#ef4444', name: 'Spam' },
          ]}
        />
      </ChartContainer>
      */}
    </ModuleContainer>
  );
};

export default BacklinkDiscovery;
