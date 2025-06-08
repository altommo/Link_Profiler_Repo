import React from 'react';
import ModuleContainer from '../shared/ModuleContainer'; // Added ModuleContainer import
import MetricDisplay from '../shared/MetricDisplay'; // Added MetricDisplay import

interface PerformanceOptimizationProps {
  metrics: {
    avg_crawl_speed_pages_per_minute: number | null;
    avg_success_rate_percentage: number | null;
    avg_response_time_ms: number | null;
    bottlenecks_detected: string[] | null; // Changed to allow null
    top_performing_satellites: string[] | null; // Changed to allow null
    worst_performing_satellites: string[] | null; // Changed to allow null
  };
}

const PerformanceOptimization: React.FC<PerformanceOptimizationProps> = ({ metrics }) => {
  return (
    <ModuleContainer title="Performance Optimization Center">
      <div className="grid grid-cols-2 gap-4 text-lg">
        <div>
          <MetricDisplay label="Avg. Crawl Speed" value={(metrics.avg_crawl_speed_pages_per_minute ?? 0).toFixed(1)} unit="pages/min" valueColorClass="text-nasa-amber" />
        </div>
        <div>
          <MetricDisplay label="Avg. Success Rate" value={(metrics.avg_success_rate_percentage ?? 0).toFixed(1)} unit="%" valueColorClass="text-nasa-cyan" />
        </div>
        <div className="col-span-2"> {/* Ensure this takes full width if needed */}
          <MetricDisplay label="Avg. Response Time" value={(metrics.avg_response_time_ms ?? 0).toFixed(0)} unit="ms" valueColorClass="text-nasa-amber" />
        </div>
      </div>

      <h3 className="text-xl font-bold text-nasa-cyan mt-6 mb-3">Bottlenecks Detected</h3>
      <div className="max-h-24 overflow-y-auto pr-2">
        {(metrics.bottlenecks_detected ?? []).length > 0 ? ( // Safely access
          (metrics.bottlenecks_detected ?? []).map((bottleneck, index) => (
            <p key={index} className="text-sm text-red-400 mb-1">{bottleneck}</p>
          ))
        ) : (
          <p className="text-nasa-light-gray text-sm">No bottlenecks detected.</p>
        )}
      </div>

      <h3 className="text-xl font-bold text-nasa-cyan mt-6 mb-3">Top Performing Satellites</h3>
      <div className="max-h-24 overflow-y-auto pr-2">
        {(metrics.top_performing_satellites ?? []).length > 0 ? ( // Safely access
          (metrics.top_performing_satellites ?? []).map((satellite, index) => (
            <p key={index} className="text-sm text-green-400 mb-1">{satellite}</p>
          ))
        ) : (
          <p className="text-nasa-light-gray text-sm">N/A</p>
        )}
      </div>

      <h3 className="text-xl font-bold text-nasa-cyan mt-6 mb-3">Worst Performing Satellites</h3>
      <div className="max-h-24 overflow-y-auto pr-2">
        {(metrics.worst_performing_satellites ?? []).length > 0 ? ( // Safely access
          (metrics.worst_performing_satellites ?? []).map((satellite, index) => (
            <p key={index} className="text-sm text-red-400 mb-1">{satellite}</p>
          ))
        ) : (
          <p className="text-nasa-light-gray text-sm">N/A</p>
        )}
      </div>
    </ModuleContainer>
  );
};

export default PerformanceOptimization;
