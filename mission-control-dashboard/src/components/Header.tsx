import React from 'react';
import { Link } from 'react-router-dom'; // Import Link from react-router-dom

const Header: React.FC = () => {
  return (
    <header className="bg-nasa-gray p-4 shadow-lg flex justify-between items-center">
      <div className="flex items-center">
        <span className="text-2xl font-bold text-nasa-cyan animate-pulseGlow">🚀</span>
        <h1 className="text-2xl font-bold ml-3">Link Profiler Mission Control</h1>
      </div>
      <nav>
        <ul className="flex space-x-4">
          <li><Link to="/overview" className="hover:text-nasa-amber transition-colors">Overview</Link></li>
          <li><Link to="/jobs" className="hover:text-nasa-amber transition-colors">Jobs</Link></li>
          <li><Link to="/alerts" className="hover:text-nasa-amber transition-colors">Alerts</Link></li>
          <li><Link to="/settings" className="hover:text-nasa-amber transition-colors">Settings</Link></li>
        </ul>
      </nav>
    </header>
  );
};

export default Header;
