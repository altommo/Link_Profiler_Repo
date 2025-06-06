import React from 'react';
import ModuleContainer from '../shared/ModuleContainer';
import ProgressBar from '../ui/ProgressBar'; // Assuming ProgressBar is in ui folder
import ChartContainer from '../shared/ChartContainer'; // New import
import LineChart from '../charts/LineChart'; // New import

interface ApiQuotaStatusProps {
  statuses: {
    api_name: string;
    limit: number;
    used: number;
    remaining: number;
    reset_date: string;
    percentage_used: number;
    status: string;
    predicted_exhaustion_date: string | null;
    recommended_action: string | null;
  }[];
}

const ApiQuotaStatus: React.FC<ApiQuotaStatusProps> = ({ statuses }) => {
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'OK': return 'text-green-500';
      case 'High Usage': return 'text-nasa-amber';
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

  // Dummy data for chart demonstration
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
                <span className={`text-sm ${getStatusColor(api.status)}`}>{api.status.toUpperCase()}</span>
              </div>
              <div className="text-sm text-nasa-light-gray mb-1">
                Used: {api.used} / {api.limit} ({api.percentage_used.toFixed(1)}%)
              </div>
              <ProgressBar percentage={api.percentage_used} colorClass={getProgressBarColor(api.percentage_used)} />
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
                Reset: {new Date(api.reset_date).toLocaleDateString()}
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
