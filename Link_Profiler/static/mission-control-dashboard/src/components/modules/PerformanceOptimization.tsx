import React from 'react';

interface PerformanceOptimizationProps {
  metrics: {
    avg_crawl_speed_pages_per_minute: number;
    avg_success_rate_percentage: number;
    avg_response_time_ms: number;
    bottlenecks_detected: string[];
    top_performing_satellites: string[];
    worst_performing_satellites: string[];
  };
}

const PerformanceOptimization: React.FC<PerformanceOptimizationProps> = ({ metrics }) => {
  return (
    <div className="bg-nasa-gray p-6 rounded-lg shadow-lg border border-nasa-cyan">
      <h2 className="text-2xl font-bold text-nasa-cyan mb-4">Performance Optimization Center</h2>
      <div className="grid grid-cols-2 gap-4 text-lg">
        <div>
          <p className="text-nasa-light-gray">Avg. Crawl Speed:</p>
          <p className="text-nasa-amber text-3xl">{metrics.avg_crawl_speed_pages_per_minute.toFixed(1)} <span className="text-base">pages/min</span></p>
        </div>
        <div>
          <p className="text-nasa-light-gray">Avg. Success Rate:</p>
          <p className="text-nasa-cyan text-3xl">{metrics.avg_success_rate_percentage.toFixed(1)}%</p>
        </div>
        <div>
          <p className="text-nasa-light-gray">Avg. Response Time:</p>
          <p className="text-nasa-amber text-3xl">{metrics.avg_response_time_ms.toFixed(0)} <span className="text-base">ms</span></p>
        </div>
      </div>

      <h3 className="text-xl font-bold text-nasa-cyan mt-6 mb-3">Bottlenecks Detected</h3>
      <div className="max-h-24 overflow-y-auto pr-2">
        {metrics.bottlenecks_detected.length > 0 ? (
          metrics.bottlenecks_detected.map((bottleneck, index) => (
            <p key={index} className="text-sm text-red-400 mb-1">{bottleneck}</p>
          ))
        ) : (
          <p className="text-nasa-light-gray text-sm">No bottlenecks detected.</p>
        )}
      </div>

      <h3 className="text-xl font-bold text-nasa-cyan mt-6 mb-3">Top Performing Satellites</h3>
      <div className="max-h-24 overflow-y-auto pr-2">
        {metrics.top_performing_satellites.length > 0 ? (
          metrics.top_performing_satellites.map((satellite, index) => (
            <p key={index} className="text-sm text-green-400 mb-1">{satellite}</p>
          ))
        ) : (
          <p className="text-nasa-light-gray text-sm">N/A</p>
        )}
      </div>

      <h3 className="text-xl font-bold text-nasa-cyan mt-6 mb-3">Worst Performing Satellites</h3>
      <div className="max-h-24 overflow-y-auto pr-2">
        {metrics.worst_performing_satellites.length > 0 ? (
          metrics.worst_performing_satellites.map((satellite, index) => (
            <p key={index} className="text-sm text-red-400 mb-1">{satellite}</p>
          ))
        ) : (
          <p className="text-nasa-light-gray text-sm">N/A</p>
        )}
      </div>
    </div>
  );
};

export default PerformanceOptimization;
