import React from 'react';

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
  return (
    <div className="bg-nasa-gray p-6 rounded-lg shadow-lg border border-nasa-cyan">
      <h2 className="text-2xl font-bold text-nasa-cyan mb-4">Backlink Discovery Operations</h2>
      <div className="grid grid-cols-2 gap-4 text-lg">
        <div>
          <p className="text-nasa-light-gray">Total Backlinks:</p>
          <p className="text-nasa-amber text-3xl">{metrics.total_backlinks_discovered}</p>
        </div>
        <div>
          <p className="text-nasa-light-gray">Unique Domains:</p>
          <p className="text-nasa-cyan text-3xl">{metrics.unique_domains_discovered}</p>
        </div>
        <div>
          <p className="text-nasa-light-gray">New (24h):</p>
          <p className="text-nasa-cyan text-3xl">{metrics.new_backlinks_24h}</p>
        </div>
        <div>
          <p className="text-nasa-light-gray">Avg. Authority Score:</p>
          <p className="text-nasa-amber text-3xl">{metrics.avg_authority_score.toFixed(1)}</p>
        </div>
        <div className="col-span-2">
          <p className="text-nasa-light-gray">Potential Spam (24h):</p>
          <p className="text-red-500 text-3xl">{metrics.potential_spam_links_24h}</p>
        </div>
      </div>

      <h3 className="text-xl font-bold text-nasa-cyan mt-6 mb-3">Top Linking Domains</h3>
      <div className="max-h-40 overflow-y-auto pr-2">
        {metrics.top_linking_domains.length > 0 ? (
          metrics.top_linking_domains.map((domain, index) => (
            <p key={index} className="text-sm text-nasa-light-gray mb-1">{domain}</p>
          ))
        ) : (
          <p className="text-nasa-light-gray text-sm">No top linking domains yet.</p>
        )}
      </div>

      <h3 className="text-xl font-bold text-nasa-cyan mt-6 mb-3">Top Target URLs</h3>
      <div className="max-h-40 overflow-y-auto pr-2">
        {metrics.top_target_urls.length > 0 ? (
          metrics.top_target_urls.map((url, index) => (
            <p key={index} className="text-sm text-nasa-light-gray mb-1 truncate">{url}</p>
          ))
        ) : (
          <p className="text-nasa-light-gray text-sm">No top target URLs yet.</p>
        )}
      </div>
    </div>
  );
};

export default BacklinkDiscovery;
