import React from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';

interface HeaderProps {
  toggleSidebar: () => void;
}

const Header: React.FC<HeaderProps> = ({ toggleSidebar }) => {
  const { user, logout } = useAuth();

  return (
    <header className="bg-nasa-medium-blue text-white p-4 flex justify-between items-center shadow-md lg:ml-64">
      <div className="flex items-center">
        <button onClick={toggleSidebar} className="text-white focus:outline-none lg:hidden mr-4">
          <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 6h16M4 12h16M4 18h16"></path>
          </svg>
        </button>
        <Link to="/" className="text-2xl font-bold text-nasa-cyan flex items-center">
          <span className="animate-pulseGlow mr-2">🚀</span> Link Profiler Mission Control
        </Link>
        {/* Status Indicators as per spec */}
        <span className="ml-6 text-sm text-nasa-light-gray flex items-center">
          <span className="w-2 h-2 bg-nasa-red rounded-full mr-1 animate-pulse"></span> LIVE
        </span>
        <span className="ml-4 text-sm text-nasa-light-gray flex items-center">
          <span className="mr-1">⚙️</span> CONFIG
        </span>
      </div>
      <div className="flex items-center">
        {user && <span className="mr-4 text-nasa-light-gray">Welcome, {user.username}</span>}
        <button
          onClick={logout}
          className="bg-nasa-red hover:bg-red-700 text-white font-bold py-2 px-4 rounded focus:outline-none focus:shadow-outline"
        >
          Logout
        </button>
      </div>
    </header>
  );
};

export default Header;
