import React from 'react';
import ModuleContainer from '../shared/ModuleContainer'; // Import ModuleContainer
import MetricDisplay from '../shared/MetricDisplay'; // Import MetricDisplay
import ListDisplay from '../shared/ListDisplay'; // Import ListDisplay

interface DomainIntelligenceProps {
  metrics: {
    total_domains_analyzed: number;
    valuable_expired_domains_found: number;
    avg_domain_value_score: number;
    new_domains_added_24h: number;
    top_niches_identified: string[];
  };
}

const DomainIntelligence: React.FC<DomainIntelligenceProps> = ({ metrics }) => {
  return (
    <ModuleContainer title="Domain Intelligence Command Center">
      <div className="grid grid-cols-2 gap-4 text-lg">
        <MetricDisplay label="Total Analyzed" value={metrics.total_domains_analyzed} valueColorClass="text-nasa-amber" />
        <MetricDisplay label="Valuable Expired" value={metrics.valuable_expired_domains_found} valueColorClass="text-nasa-cyan" />
        <MetricDisplay label="Avg. Value Score" value={metrics.avg_domain_value_score.toFixed(1)} valueColorClass="text-nasa-amber" />
        <MetricDisplay label="New (24h)" value={metrics.new_domains_added_24h} valueColorClass="text-nasa-cyan" />
      </div>

      <ListDisplay
        title="Top Niches Identified"
        items={metrics.top_niches_identified}
        emptyMessage="No top niches identified yet."
        maxHeight="max-h-40"
      />
    </ModuleContainer>
  );
};

export default DomainIntelligence;
