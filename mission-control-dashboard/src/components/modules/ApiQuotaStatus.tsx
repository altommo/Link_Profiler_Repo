import React from 'react';
import ModuleContainer from '../shared/ModuleContainer';
import ProgressBar from '../ui/ProgressBar';
import ChartContainer from '../shared/ChartContainer';
import LineChart from '../../charts/LineChart'; // Corrected import path for LineChart
import MetricDisplay from '../shared/MetricDisplay'; // Import MetricDisplay

interface ApiPerformanceMetrics {
  total_calls: number;
  successful_calls: number;
  average_response_time_ms: number;
  success_rate: number;
  circuit_breaker_state: string; // Added circuit_breaker_state
}

interface ApiQuotaStatusItem {
  api_name: string; // Added api_name
  limit: number;
  used: number;
  remaining: number | null;
  reset_day_of_month: number; // Added reset_day_of_month
  last_reset_date: string; // Changed to string as it's isoformat
  quality_score: number; // Added quality_score
  supported_query_types: string[]; // Added supported_query_types
  cost_per_unit: number; // Added cost_per_unit
  percentage_used: number;
  status?: string; // Added status, made optional as it might be derived
  predicted_exhaustion_date: string | null;
  recommended_action?: string | null; // Made optional
  performance: ApiPerformanceMetrics; // New: Nested performance metrics
}

interface ApiQuotaStatusProps {
  statuses: ApiQuotaStatusItem[];
}

const ApiQuotaStatus: React.FC<ApiQuotaStatusProps> = ({ statuses }) => {
  const getStatusColor = (status: string | undefined) => { // Updated to handle undefined
    switch (status) {
      case 'OK': return 'text-green-500';
      case 'Warning': return 'text-nasa-amber';
      case 'Critical': return 'text-red-500';
      default: return 'text-nasa-light-gray';
    }
  };

  const getProgressBarColor = (percentage: number) => {
    if (percentage >= 90) return 'bg-red-500';
    if (percentage >= 75) return 'bg-nasa-amber';
    return 'bg-green-500';
  };

  // Prepare data for the chart
  const apiUsageHistory = statuses.map(api => ({
    name: api.api_name,
    usage: api.percentage_used,
  }));

  return (
    <ModuleContainer title="API Quota Management">
      <div className="space-y-4">
        {statuses.length > 0 ? (
          statuses.map((api) => (
            <div key={api.api_name} className="border border-nasa-light-gray p-3 rounded-md">
              <div className="flex justify-between items-center mb-1">
                <span className="text-lg font-semibold">{api.api_name}</span>
                <span className={`text-sm ${getStatusColor(api.status)}`}>{api.status ? api.status.toUpperCase() : 'N/A'}</span>
              </div>
              <div className="grid grid-cols-2 gap-2 text-sm text-nasa-light-gray">
                <MetricDisplay label="Used" value={`${api.used} / ${api.limit === -1 ? 'Unlimited' : api.limit}`} />
                <MetricDisplay label="Remaining" value={api.remaining === null ? 'Unlimited' : api.remaining} />
                <MetricDisplay label="Success Rate" value={`${(api.performance.success_rate * 100).toFixed(1)}%`} valueColorClass={api.performance.success_rate < 0.9 ? 'text-red-500' : 'text-green-500'} />
                <MetricDisplay label="Avg. Response" value={`${api.performance.average_response_time_ms.toFixed(0)}ms`} valueColorClass={api.performance.average_response_time_ms > 1000 ? 'text-red-500' : 'text-green-500'} />
              </div>
              <ProgressBar percentage={api.percentage_used} colorClass={getProgressBarColor(api.percentage_used)} className="mt-2" />
              <p className="text-xs text-nasa-light-gray mt-1">{api.percentage_used.toFixed(1)}% Used</p>
              {api.predicted_exhaustion_date && (
                <p className="text-xs text-nasa-light-gray mt-1">
                  Exhaustion: {new Date(api.predicted_exhaustion_date).toLocaleDateString()}
                </p>
              )}
              {api.recommended_action && (
                <p className="text-xs text-nasa-amber mt-1">
                  Action: {api.recommended_action}
                </p>
              )}
              <p className="text-xs text-nasa-light-gray mt-1">
                Reset: {new Date(api.last_reset_date).toLocaleDateString()}
              </p>
            </div>
          ))
        ) : (
          <p className="text-nasa-light-gray text-sm">No API quota data available.</p>
        )}
      </div>

      {statuses.length > 0 && (
        <ChartContainer title="Current API Usage (%)">
          <LineChart
            data={apiUsageHistory}
            dataKey="name"
            lineKeys={[{ key: 'usage', stroke: '#00FFFF', name: 'Usage %' }]}
            yAxisTickFormatter={(value) => `${value}%`}
          />
        </ChartContainer>
      )}
    </ModuleContainer>
  );
};

export default ApiQuotaStatus;
