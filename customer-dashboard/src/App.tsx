import { Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/layout/Layout';
import { useAuth } from './hooks/useAuth';

// Page components
import Dashboard from './components/Dashboard';
import CrawlJobs from './components/CrawlJobs';
import UserProfile from './components/UserProfile';
import Login from './components/Login';

const ProtectedRoute: React.FC<{ children: JSX.Element }> = ({ children }) => {
  const { isAuthenticated, loading } = useAuth();

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-nasa-dark-blue"> {/* Changed background to nasa-dark-blue */}
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-nasa-cyan mx-auto"></div> {/* Changed border color */}
          <p className="mt-4 text-nasa-light-gray">Authenticating...</p> {/* Changed text color */}
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return children;
};

function App() {
  const { isAuthenticated } = useAuth();

  return (
    <div className="min-h-screen bg-nasa-dark-blue"> {/* Changed background to nasa-dark-blue for consistency */}
      {isAuthenticated ? (
        <Layout>
          <Routes>
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="/dashboard" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
            <Route path="/jobs" element={<ProtectedRoute><CrawlJobs /></ProtectedRoute>} />
            <Route path="/profile" element={<ProtectedRoute><UserProfile /></ProtectedRoute>} />
            <Route path="*" element={<Navigate to="/dashboard" replace />} />
          </Routes>
        </Layout>
      ) : (
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="*" element={<Navigate to="/login" replace />} />
        </Routes>
      )}
    </div>
  );
}

export default App;
