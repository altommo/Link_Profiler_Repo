import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { AUTH_ENDPOINTS } from '../config';

const Login: React.FC = () => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      // The login function in AuthContext now handles the API call directly
      await login(username, password); 
      navigate('/'); // Redirect to dashboard on successful login
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-container min-h-screen flex items-center justify-center bg-nasa-dark-blue">
      <div className="login-card bg-nasa-medium-blue p-8 rounded-lg shadow-lg w-full max-w-md">
        <h1 className="login-title text-3xl font-bold text-nasa-cyan text-center mb-2">Link Profiler Mission Control</h1>
        <p className="login-subtitle text-nasa-light-gray text-center mb-6">Admin Login</p>
        <form onSubmit={handleSubmit} className="login-form">
          <div className="form-group mb-4">
            <label htmlFor="username" className="block text-nasa-light-gray text-sm font-bold mb-2">Username:</label>
            <input
              type="text"
              id="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              className="form-input shadow appearance-none border rounded w-full py-2 px-3 text-nasa-dark-blue leading-tight focus:outline-none focus:shadow-outline bg-nasa-light-gray border-nasa-light-gray"
            />
          </div>
          <div className="form-group mb-6">
            <label htmlFor="password" className="block text-nasa-light-gray text-sm font-bold mb-2">Password:</label>
            <input
              type="password"
              id="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              className="form-input shadow appearance-none border rounded w-full py-2 px-3 text-nasa-dark-blue leading-tight focus:outline-none focus:shadow-outline bg-nasa-light-gray border-nasa-light-gray"
            />
          </div>
          {error && <p className="text-nasa-red text-sm mb-4">{error}</p>}
          <button
            type="submit"
            className="login-button bg-nasa-cyan hover:bg-nasa-blue text-nasa-dark-blue font-bold py-2 px-4 rounded focus:outline-none focus:shadow-outline w-full"
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
