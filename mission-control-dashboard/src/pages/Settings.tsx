import React from 'react';
import DataCard from '../components/ui/DataCard';

const Settings: React.FC = () => {
  return (
    <div className="space-y-8">
      <h1 className="text-4xl font-bold text-nasa-cyan mb-4">System Settings</h1>
      <DataCard title="General Configuration">
        <p className="text-nasa-light-gray text-lg">
          This section will allow configuration of various system settings, such as API keys,
          crawler defaults, and notification preferences.
        </p>
        {/* Future: Add forms for configuration */}
      </DataCard>
      <DataCard title="User Management">
        <p className="text-nasa-light-gray text-lg">
          Manage user accounts and permissions here.
        </p>
        {/* Future: Add user management interface */}
      </DataCard>
    </div>
  );
};

export default Settings;
