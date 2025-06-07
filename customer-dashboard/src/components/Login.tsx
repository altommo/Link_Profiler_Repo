import React, { useState } from 'react';
import { useAuth } from '../hooks/useAuth';

const Login: React.FC = () => {
  const [username, setUsername] = useState<string>('');
  const [password, setPassword] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string>(''); // Initialize as empty string

  const { login } = useAuth();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      await login(username, password);
    } catch (err: any) {
      setError(err.message || 'Invalid username or password');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-container"> {/* Applied custom class */}
      <div className="login-card"> {/* Applied custom class */}
        <div>
          <h2 className="login-title"> {/* Applied custom class */}
            Sign in to your account
          </h2>
          <p className="login-subtitle"> {/* Applied custom class */}
            Access your Link Profiler dashboard
          </p>
        </div>
        <form className="login-form" onSubmit={handleSubmit}> {/* Applied custom class */}
          <div className="rounded-md shadow-sm -space-y-px">
            <div className="form-group"> {/* Applied custom class */}
              <label htmlFor="username" className="sr-only">
                Username
              </label>
              <input
                id="username"
                name="username"
                type="text"
                required
                className="form-input" {/* Applied custom class */}
                placeholder="Username"
                value={username}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setUsername(e.target.value)}
              />
            </div>
            <div className="form-group"> {/* Applied custom class */}
              <label htmlFor="password" className="sr-only">
                Password
              </label>
              <input
                id="password"
                name="password"
                type="password"
                required
                className="form-input rounded-b-md" {/* Applied custom class, kept rounded-b-md */}
                placeholder="Password"
                value={password}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setPassword(e.target.value)}
              />
            </div>
          </div>

          {error && (
            <div className="error-message"> {/* Applied custom class */}
              {error}
            </div>
          )}

          <div>
            <button
              type="submit"
              disabled={loading}
              className="login-button" {/* Applied custom class */}
            >
              {loading ? 'Signing in...' : 'Sign in'}
            </button>
          </div>

          <div className="text-center mt-4"> {/* Added margin-top */}
            <p className="text-sm text-nasa-light-gray"> {/* Changed text color */}
              Don't have an account?{' '}
              <a href="/register" className="font-medium text-nasa-cyan hover:text-nasa-blue"> {/* Changed text color */}
                Contact support
              </a>
            </p>
          </div>
        </form>
      </div>
    </div>
  );
};

export default Login;
