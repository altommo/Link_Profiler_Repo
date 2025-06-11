// src/contexts/AuthContext.tsx
import React, { createContext, useState, useEffect, ReactNode, useCallback, useContext } from 'react';
import { User, Token } from '../types';
import { AUTH_ENDPOINTS } from '../config';

interface AuthContextType {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  isCustomer: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  loading: boolean;
}

export const AuthContext = createContext<AuthContextType | undefined>(undefined);

interface AuthProviderProps {
  children: ReactNode;
}

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(localStorage.getItem('access_token'));
  const [loading, setLoading] = useState<boolean>(true);

  const isAuthenticated = !!user && !!token;
  const isCustomer = user?.role === 'customer' || false;

  const verifyToken = useCallback(async (currentToken: string) => {
    console.log("AuthContext - Verifying token...");
    try {
      const response = await fetch(AUTH_ENDPOINTS.verify, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${currentToken}`,
          'Content-Type': 'application/json',
        },
      });

      if (response.ok) {
        const userData: User = await response.json();
        setUser(userData);
        console.log("AuthContext - Token verified, user set:", userData.username, "role:", userData.role);
        return true;
      } else {
        console.error('AuthContext - Token verification failed:', response.status, response.statusText);
        localStorage.removeItem('access_token');
        setToken(null);
        setUser(null);
        return false;
      }
    } catch (error) {
      console.error('AuthContext - Error verifying token:', error);
      localStorage.removeItem('access_token');
      setToken(null);
      setUser(null);
      return false;
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    console.log("AuthContext - useEffect triggered. Token:", token);
    const initializeAuth = async () => {
      if (token) {
        await verifyToken(token);
      } else {
        setLoading(false);
      }
    };
    initializeAuth();
  }, [token, verifyToken]);

  const login = async (username: string, password: string) => {
    setLoading(true);
    console.log("AuthContext - Attempting login for:", username);
    try {
      const formData = new URLSearchParams();
      formData.append('username', username);
      formData.append('password', password);

      const response = await fetch(AUTH_ENDPOINTS.login, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: formData.toString(),
      });

      if (response.ok) {
        const data: Token = await response.json();
        localStorage.setItem('access_token', data.access_token);
        setToken(data.access_token);

        // Wait for the token verification to complete
        await verifyToken(data.access_token);

        console.log("AuthContext - Login successful, token and user set.");
      } else {
        const errorData = await response.json();
        console.error("AuthContext - Login failed:", errorData.detail || response.statusText);
        throw new Error(errorData.detail || 'Login failed');
      }
    } catch (error) {
      console.error('AuthContext - Login error:', error);
      throw error;
    } finally {
      setLoading(false);
    }
  };

  const logout = () => {
    console.log("AuthContext - Logging out.");
    localStorage.removeItem('access_token');
    setToken(null);
    setUser(null);
    setLoading(false);
  };

  const contextValue = {
    user,
    token,
    isAuthenticated,
    isCustomer,
    login,
    logout,
    loading,
  };

  return (
    <AuthContext.Provider value={contextValue}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
