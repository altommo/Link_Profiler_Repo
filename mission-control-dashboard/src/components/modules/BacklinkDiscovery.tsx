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
    avg_authority_score: number;
    top_linking_domains: string[];
    top_target_urls: string[];
    potential_spam_links_24h: number;
  };
}

const BacklinkDiscovery: React.FC<BacklinkDiscoveryProps> = ({ metrics }) => {
  // Dummy data for chart demonstration
  const discoveryRateData = [
    { name: 'Day 1', discovered: 50, spam: 5 },
    { name: 'Day 2', discovered: 70, spam: 8 },
    { name: 'Day 3', discovered: 60, spam: 6 },
    { name: 'Day 4', discovered: 80, spam: 10 },
    { name: 'Day 5', discovered: 75, spam: 7 },
    { name: 'Day 6', discovered: 90, spam: 9 },
    { name: 'Day 7', discovered: metrics.new_backlinks_24h, spam: metrics.potential_spam_links_24h },
  ];

  return (
    <ModuleContainer title="Backlink Discovery Operations">
      <div className="grid grid-cols-2 gap-4 text-lg">
        <MetricDisplay label="Total Backlinks" value={metrics.total_backlinks_discovered} valueColorClass="text-nasa-amber" />
        <MetricDisplay label="Unique Domains" value={metrics.unique_domains_discovered} valueColorClass="text-nasa-cyan" />
        <MetricDisplay label="New (24h)" value={metrics.new_backlinks_24h} valueColorClass="text-nasa-cyan" />
        <MetricDisplay label="Avg. Authority Score" value={metrics.avg_authority_score.toFixed(1)} valueColorClass="text-nasa-amber" />
        <div className="col-span-2">
          <MetricDisplay label="Potential Spam (24h)" value={metrics.potential_spam_links_24h} valueColorClass="text-red-500" />
        </div>
      </div>

      <ListDisplay
        title="Top Linking Domains"
        items={metrics.top_linking_domains}
        emptyMessage="No top linking domains yet."
        maxHeight="max-h-40"
      />

      <ListDisplay
        title="Top Target URLs"
        items={metrics.top_target_urls}
        emptyMessage="No top target URLs yet."
        maxHeight="max-h-40"
      />

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
    </ModuleContainer>
  );
};

export default BacklinkDiscovery;
