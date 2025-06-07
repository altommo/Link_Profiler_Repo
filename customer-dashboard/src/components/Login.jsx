import React, { useState } from 'react';
// Assuming you'll have an API service for login
// import { loginUser } from '../services/api'; 

const Login = ({ onLogin }) => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      // In a real application, you'd send credentials to your backend API
      // const response = await loginUser(username, password);
      
      // Simulate API call
      await new Promise(resolve => setTimeout(resolve, 1000)); // Simulate network delay
      if (username === 'customer' && password === 'password') {
        const userData = { username: 'customer', email: 'customer@example.com', role: 'customer' };
        onLogin(userData);
      } else {
        throw new Error('Invalid username or password');
      }
    } catch (err) {
      setError(err.message || 'Login failed. Please check your credentials.');
      console.error('Login error:', err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-container">
      <h2>Login to Customer Dashboard</h2>
      <p>Please enter your credentials to access your account.</p>

      {error && <div className="error-message">{error}</div>}

      <form onSubmit={handleSubmit} className="login-form">
        <div className="form-group">
          <label htmlFor="username">Username:</label>
          <input
            type="text"
            id="username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
            disabled={loading}
          />
        </div>
        <div className="form-group">
          <label htmlFor="password">Password:</label>
          <input
            type="password"
            id="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            disabled={loading}
          />
        </div>
        <button type="submit" className="login-button" disabled={loading}>
          {loading ? 'Logging in...' : 'Login'}
        </button>
      </form>

      <p className="register-link">
        Don't have an account? <a href="/register">Register here</a> (Not implemented yet).
      </p>
    </div>
  );
};

export default Login;
