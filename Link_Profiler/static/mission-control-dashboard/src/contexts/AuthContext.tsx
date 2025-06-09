// src/contexts/AuthContext.tsx
import React, { createContext, useState, useEffect, ReactNode, useCallback, useContext } from 'react';
import { User, Token } from '../types'; // Assuming User and Token types are defined in types.ts
import { AUTH_ENDPOINTS } from '../config';

interface AuthContextType {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  isAdmin: boolean;
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
  const isAdmin = user?.is_admin || false;

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
        console.log("AuthContext - Token verified, user set:", userData.username);
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
    }
  }, []);

  useEffect(() => {
    console.log("AuthContext - useEffect triggered. Token:", token);
    const initializeAuth = async () => {
      if (token) {
        await verifyToken(token);
      }
      setLoading(false); // Always set loading to false after initialization
    };
    initializeAuth();
  }, [token, verifyToken]);

  const login = async (username: string, password: string) => {
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
        console.log("AuthContext - Login successful, token set.");
        // Don't set loading here - let useEffect handle it
      } else {
        const errorData = await response.json();
        console.error("AuthContext - Login failed:", errorData.detail || response.statusText);
        throw new Error(errorData.detail || 'Login failed');
      }
    } catch (error) {
      console.error('AuthContext - Login error:', error);
      throw error; // Re-throw to be caught by the login component
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
    isAdmin,
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
