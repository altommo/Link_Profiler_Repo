import Layout from './components/Layout';
import useRealTimeData from './hooks/useRealTimeData';
import useMissionControlStore from './stores/missionControlStore';
import Dashboard from './pages/Dashboard'; // Import the new Dashboard page

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
        
        {/* Render the main Dashboard page */}
        <Dashboard />
      </Layout>
    </div>
  );
}

export default App;
