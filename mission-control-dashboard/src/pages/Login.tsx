import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { AUTH_ENDPOINTS } from '../config';

const Login: React.FC = () => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const { login, loading } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    try {
      const response = await fetch(AUTH_ENDPOINTS.login, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: new URLSearchParams({
          username: username,
          password: password,
        }).toString(),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Login failed');
      }

      const data = await response.json();
      await login(data.access_token); // Use the login function from AuthContext
      navigate('/'); // Redirect to dashboard on successful login
    } catch (err: any) {
      setError(err.message);
    }
  };

  return (
    <div className="login-container min-h-screen flex items-center justify-center bg-gray-900">
      <div className="login-card bg-gray-800 p-8 rounded-lg shadow-lg w-full max-w-md">
        <h1 className="login-title text-3xl font-bold text-white text-center mb-2">Link Profiler Mission Control</h1>
        <p className="login-subtitle text-gray-400 text-center mb-6">Admin Login</p>
        <form onSubmit={handleSubmit} className="login-form">
          <div className="form-group mb-4">
            <label htmlFor="username" className="block text-gray-300 text-sm font-bold mb-2">Username:</label>
            <input
              type="text"
              id="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              className="form-input shadow appearance-none border rounded w-full py-2 px-3 text-gray-700 leading-tight focus:outline-none focus:shadow-outline bg-gray-700 border-gray-600"
            />
          </div>
          <div className="form-group mb-6">
            <label htmlFor="password" className="block text-gray-300 text-sm font-bold mb-2">Password:</label>
            <input
              type="password"
              id="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              className="form-input shadow appearance-none border rounded w-full py-2 px-3 text-gray-700 leading-tight focus:outline-none focus:shadow-outline bg-gray-700 border-gray-600"
            />
          </div>
          {error && <p className="text-red-500 text-sm mb-4">{error}</p>}
          <button
            type="submit"
            className="login-button bg-nasa-blue hover:bg-nasa-dark-blue text-white font-bold py-2 px-4 rounded focus:outline-none focus:shadow-outline w-full"
            disabled={loading}
          >
            {loading ? 'Logging in...' : 'Login'}
          </button>
        </form>
      </div>
    </div>
  );
};

export default Login;
