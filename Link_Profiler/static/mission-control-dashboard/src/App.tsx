import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { useAuth } from './contexts/AuthContext';
import Layout from './components/layout/Layout';
import Dashboard from './pages/Dashboard';
import Jobs from './pages/Jobs';
import Settings from './pages/Settings';
import Login from './pages/Login';
import Overview from './pages/Overview'; // Import the new Overview page

const App: React.FC = () => {
  const { isAuthenticated, isAdmin, loading } = useAuth();

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-900 text-white">
        Loading application...
      </div>
    );
  }

  return (
    <Router>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          path="/"
          element={
            isAuthenticated ? (
              <Layout>
                <Routes>
                  <Route path="/" element={<Overview />} /> {/* Default route to Overview */}
                  <Route path="/dashboard" element={<Dashboard />} />
                  <Route path="/jobs" element={<Jobs />} />
                  {isAdmin && <Route path="/settings" element={<Settings />} />}
                  <Route path="*" element={<Navigate to="/" replace />} />
                </Routes>
              </Layout>
            ) : (
              <Navigate to="/login" replace />
            )
          }
        />
      </Routes>
    </Router>
  );
};

export default App;
