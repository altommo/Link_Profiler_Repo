import React from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import ModuleContainer from '../shared/ModuleContainer';
import ProgressBar from '../ui/ProgressBar';
import MetricDisplay from '../shared/MetricDisplay';
import { ApiQuotaStatus as ApiQuotaStatusType } from '../../types'; // Use the imported type

interface ApiQuotaStatusProps {
  statuses: ApiQuotaStatusType[]; // Use the imported type
}

const ApiQuotaStatus: React.FC<ApiQuotaStatusProps> = ({ statuses }) => {
  const getProgressBarColor = (percentage: number) => {
    if (percentage >= 90) return 'bg-red-500';
    if (percentage >= 70) return 'bg-orange-500';
    return 'bg-green-500';
  };

  // Prepare data for the LineChart
  const chartData = statuses.map(api => ({
    name: api.api_name,
    'Usage (%)': api.percentage_used,
    'Avg Response Time (ms)': api.performance?.average_response_time_ms || 0, // Make performance optional
    'Success Rate (%)': (api.performance?.success_rate || 0) * 100, // Make performance optional
  }));

  return (
    <ModuleContainer title="API Quota & Performance">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        {statuses.map((api) => (
          <div key={api.api_name} className="bg-gray-800 p-4 rounded-lg shadow-md">
            <h3 className="text-lg font-semibold text-white mb-2">{api.api_name}</h3>
            <div className="flex justify-between items-center mb-2">
              <MetricDisplay label="Used" value={`${api.used}/${api.limit}`} valueColorClass="text-blue-400" />
              <MetricDisplay label="Remaining" value={api.remaining !== undefined ? api.remaining : 'N/A'} valueColorClass="text-purple-400" />
            </div>
            <ProgressBar percentage={api.percentage_used} colorClass={getProgressBarColor(api.percentage_used)} className="mt-2" />
            <p className="text-sm text-gray-400 mt-1">Reset: {new Date(api.reset_date).toLocaleDateString()}</p>
            {api.predicted_exhaustion_date && (
              <p className="text-sm text-gray-400">Exhaustion: {new Date(api.predicted_exhaustion_date).toLocaleDateString()}</p>
            )}
            {api.performance && ( // Only render if performance data exists
              <div className="mt-4 text-sm text-gray-300">
                <p>Total Calls: {api.performance.total_calls}</p>
                <p>Successful Calls: {api.performance.successful_calls}</p>
                <p>Avg. Response Time: {api.performance.average_response_time_ms.toFixed(2)} ms</p>
                <p>Success Rate: {(api.performance.success_rate * 100).toFixed(2)}%</p>
                <p>Circuit Breaker: <span className={`font-semibold ${api.performance.circuit_breaker_state === 'OPEN' ? 'text-red-500' : 'text-green-500'}`}>{api.performance.circuit_breaker_state}</span></p>
              </div>
            )}
          </div>
        ))}
      </div>

      <h3 className="text-xl font-semibold text-white mb-4">API Performance Trends</h3>
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={chartData} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#444" />
          <XAxis dataKey="name" stroke="#999" />
          <YAxis yAxisId="left" stroke="#999" label={{ value: 'Usage (%)', angle: -90, position: 'insideLeft', fill: '#999' }} />
          <YAxis yAxisId="right" orientation="right" stroke="#999" label={{ value: 'Time (ms) / Rate (%)', angle: 90, position: 'insideRight', fill: '#999' }} />
          <Tooltip
            contentStyle={{ backgroundColor: '#333', border: 'none', color: '#fff' }}
            labelStyle={{ color: '#fff' }}
            formatter={(value: string | number, name: string) => [`${value}${name.includes('Time') ? 'ms' : '%'}`, name]}
          />
          <Line yAxisId="left" type="monotone" dataKey="Usage (%)" stroke="#8884d8" activeDot={{ r: 8 }} />
          <Line yAxisId="right" type="monotone" dataKey="Avg Response Time (ms)" stroke="#82ca9d" />
          <Line yAxisId="right" type="monotone" dataKey="Success Rate (%)" stroke="#ffc658" />
        </LineChart>
      </ResponsiveContainer>
    </ModuleContainer>
  );
};

export default ApiQuotaStatus;
