import React from 'react';
import DataCard from '../components/ui/DataCard';
import useMissionControlStore from '../stores/missionControlStore';
import AlertsDisplay from '../components/modules/AlertsDisplay'; // Re-use the AlertsDisplay module

const Alerts: React.FC = () => {
  const { data } = useMissionControlStore();

  if (!data) {
    return (
      <div className="text-center text-nasa-light-gray text-xl mt-20">
        <p>Awaiting data streams from Mission Control...</p>
        <p className="text-sm mt-2">Ensure backend services are running and WebSocket is connected.</p>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <h1 className="text-4xl font-bold text-nasa-cyan mb-4">System Alerts & Notifications</h1>
      <DataCard title="Active System Alerts">
        <AlertsDisplay alerts={data.alerts} />
      </DataCard>
      {/* Future: Add historical alerts, alert configuration, etc. */}
      <div className="text-nasa-light-gray text-lg mt-8">
        <p>This page will display detailed historical alerts and allow for alert rule configuration.</p>
      </div>
    </div>
  );
};

export default Alerts;
