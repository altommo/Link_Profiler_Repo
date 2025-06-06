import Layout from './components/Layout';
import useRealTimeData from './hooks/useRealTimeData';
import useMissionControlStore from './stores/missionControlStore';
import { Routes, Route, Navigate } from 'react-router-dom';

// Page components
import Overview from './pages/Overview';
import Jobs from './pages/Jobs'; // New import

function App() {
  const { isConnected } = useRealTimeData();
  const { data, lastUpdated } = useMissionControlStore();

  return (
    <div className="min-h-screen flex flex-col">
      <Layout>
        {/* Display connection status at the top of the layout */}
        <div className="text-right text-sm text-nasa-light-gray mb-4">
          Connection Status: <span className={isConnected ? 'text-green-500' : 'text-red-500'}>
            {isConnected ? 'ONLINE' : 'OFFLINE'}
          </span>
          {lastUpdated && (
            <span className="ml-4">Last Data Received: {new Date(lastUpdated).toLocaleTimeString()}</span>
          )}
        </div>
        
        {/* Define routes */}
        <Routes>
          <Route path="/" element={<Navigate to="/overview" replace />} />
          <Route path="/overview" element={<Overview />} />
          <Route path="/jobs" element={<Jobs />} /> {/* New Jobs page route */}
          {/* Add more routes for Alerts, Settings etc. in future turns */}
        </Routes>
      </Layout>
    </div>
  );
}

export default App;
