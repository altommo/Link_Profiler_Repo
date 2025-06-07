import { Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/layout/Layout'; // Corrected import path
import useRealTimeData from './hooks/useRealTimeData';
import useMissionControlStore from './stores/missionControlStore';
import { useAuth } from './hooks/useAuth'; // Import useAuth

// Page components
import Overview from './pages/Overview';
import Jobs from './pages/Jobs';
import Alerts from './pages/Alerts';
import Settings from './pages/Settings';
import Login from './pages/Login'; // Import Login page

const ProtectedRoute: React.FC<{ children: JSX.Element, adminOnly?: boolean }> = ({ children, adminOnly = false }) => {
  const { isAuthenticated, isAdmin, loading } = useAuth();

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-nasa-dark-blue text-nasa-light-gray">
        <p className="text-xl">Authenticating...</p>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  if (adminOnly && !isAdmin) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-nasa-dark-blue text-red-500">
        <p className="text-xl">Access Denied: Administrator privileges required.</p>
      </div>
    );
  }

  return children;
};

function App() {
  const { isConnected } = useRealTimeData();
  const { lastUpdated } = useMissionControlStore(); // Removed 'data' as it's not directly used here
  const { isAuthenticated } = useAuth(); // Use isAuthenticated from useAuth

  return (
    <div className="min-h-screen flex flex-col">
      {/* Only render Layout if authenticated, otherwise Login page handles its own layout */}
      {isAuthenticated ? (
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
            <Route path="/overview" element={<ProtectedRoute><Overview /></ProtectedRoute>} />
            <Route path="/jobs" element={<ProtectedRoute><Jobs /></ProtectedRoute>} />
            <Route path="/alerts" element={<ProtectedRoute><Alerts /></ProtectedRoute>} />
            <Route path="/settings" element={<ProtectedRoute adminOnly><Settings /></ProtectedRoute>} /> {/* Settings is admin-only */}
            {/* Catch-all for unmatched routes within the dashboard context */}
            <Route path="*" element={<Navigate to="/overview" replace />} />
          </Routes>
        </Layout>
      ) : (
        <Routes>
          <Route path="/login" element={<Login />} />
          {/* Redirect any other unauthenticated path to login */}
          <Route path="*" element={<Navigate to="/login" replace />} />
        </Routes>
      )}
    </div>
  );
}

export default App;
