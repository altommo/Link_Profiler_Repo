import React from 'react';
import { DashboardAlert } from '../../types'; // Import DashboardAlert type

interface AlertsDisplayProps {
  alerts: DashboardAlert[]; // Use the imported DashboardAlert type
}

const AlertsDisplay: React.FC<AlertsDisplayProps> = ({ alerts }) => {
  const getSeverityColor = (severity: string) => {
    switch (severity.toLowerCase()) {
      case 'critical': return 'text-nasa-red';
      case 'high': return 'text-nasa-red'; // High also red
      case 'warning': return 'text-nasa-amber';
      case 'low': return 'text-nasa-cyan';
      default: return 'text-nasa-light-gray';
    }
  };

  const getSeverityBorderColor = (severity: string) => {
    switch (severity.toLowerCase()) {
      case 'critical': return 'border-nasa-red';
      case 'high': return 'border-nasa-red';
      case 'warning': return 'border-nasa-amber';
      case 'low': return 'border-nasa-cyan';
      default: return 'border-nasa-light-gray';
    }
  };

  return (
    <div className="bg-nasa-medium-blue p-6 rounded-lg shadow-lg border border-nasa-cyan col-span-full">
      <h2 className="text-2xl font-bold text-nasa-cyan mb-4">System Alerts</h2>
      <div className="max-h-60 overflow-y-auto pr-2 space-y-3">
        {alerts.length > 0 ? (
          alerts.map((alert, index) => (
            <div key={index} className={`p-3 rounded-md border ${getSeverityBorderColor(alert.severity)}`}>
              <div className="flex justify-between items-center mb-1">
                <span className={`font-semibold ${getSeverityColor(alert.severity)}`}>
                  {alert.source.toUpperCase()} ({alert.severity.toUpperCase()})
                </span>
                <span className="text-xs text-nasa-light-gray">
                  {new Date(alert.timestamp).toLocaleTimeString()}
                </span>
              </div>
              <p className="text-sm text-nasa-light-gray">{alert.message}</p>
              {alert.recommended_action && (
                <p className="text-xs text-nasa-amber mt-1">
                  Action: {alert.recommended_action}
                </p>
              )}
              {alert.details && (
                <details className="text-xs text-nasa-light-gray mt-1">
                  <summary>Details</summary>
                  <pre className="overflow-x-auto text-xs bg-nasa-dark-blue p-1 rounded mt-1">
                    {JSON.stringify(alert.details, null, 2)}
                  </pre>
                </details>
              )}
            </div>
          ))
        ) : (
          <p className="text-nasa-light-gray text-lg">All systems nominal. No active alerts.</p>
        )}
      </div>
    </div>
  );
};

export default AlertsDisplay;
