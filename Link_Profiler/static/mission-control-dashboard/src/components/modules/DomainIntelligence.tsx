import React from 'react';

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
    <div className="bg-nasa-gray p-6 rounded-lg shadow-lg border border-nasa-cyan">
      <h2 className="text-2xl font-bold text-nasa-cyan mb-4">Domain Intelligence Command Center</h2>
      <div className="grid grid-cols-2 gap-4 text-lg">
        <div>
          <p className="text-nasa-light-gray">Total Analyzed:</p>
          <p className="text-nasa-amber text-3xl">{metrics.total_domains_analyzed}</p>
        </div>
        <div>
          <p className="text-nasa-light-gray">Valuable Expired:</p>
          <p className="text-nasa-cyan text-3xl">{metrics.valuable_expired_domains_found}</p>
        </div>
        <div>
          <p className="text-nasa-light-gray">Avg. Value Score:</p>
          <p className="text-nasa-amber text-3xl">{metrics.avg_domain_value_score.toFixed(1)}</p>
        </div>
        <div>
          <p className="text-nasa-light-gray">New (24h):</p>
          <p className="text-nasa-cyan text-3xl">{metrics.new_domains_added_24h}</p>
        </div>
      </div>

      <h3 className="text-xl font-bold text-nasa-cyan mt-6 mb-3">Top Niches Identified</h3>
      <div className="max-h-40 overflow-y-auto pr-2">
        {metrics.top_niches_identified.length > 0 ? (
          metrics.top_niches_identified.map((niche, index) => (
            <p key={index} className="text-sm text-nasa-light-gray mb-1">{niche}</p>
          ))
        ) : (
          <p className="text-nasa-light-gray text-sm">No top niches identified yet.</p>
        )}
      </div>
    </div>
  );
};

export default DomainIntelligence;
