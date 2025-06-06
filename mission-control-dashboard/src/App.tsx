import Layout from './components/Layout';
import useRealTimeData from './hooks/useRealTimeData';
import useMissionControlStore from './stores/missionControlStore';

function App() {
  const { isConnected } = useRealTimeData();
  const { data, lastUpdated } = useMissionControlStore();

  return (
    <div className="min-h-screen flex flex-col">
      <Layout>
        <h1 className="text-4xl font-bold text-nasa-cyan mb-8">Mission Control Dashboard</h1>
        <p className="text-lg text-nasa-light-gray mb-4">
          Status: <span className={isConnected ? 'text-green-500' : 'text-red-500'}>
            {isConnected ? 'ONLINE' : 'OFFLINE'}
          </span>
        </p>
        {lastUpdated && (
          <p className="text-sm text-nasa-light-gray mb-4">
            Last Updated: {new Date(lastUpdated).toLocaleTimeString()}
          </p>
        )}
        
        {data ? (
          <div className="bg-nasa-gray p-6 rounded-lg shadow-lg">
            <h2 className="text-2xl font-bold text-nasa-cyan mb-4">Real-time Data</h2>
            <pre className="text-nasa-cyan text-sm overflow-auto max-h-[600px]">
              {JSON.stringify(data, null, 2)}
            </pre>
          </div>
        ) : (
          <p className="text-lg text-nasa-light-gray">Awaiting data streams...</p>
        )}
      </Layout>
    </div>
  );
}

export default App;
