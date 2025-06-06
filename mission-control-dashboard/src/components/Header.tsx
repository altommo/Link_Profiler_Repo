import React from 'react';

const Header: React.FC = () => {
  return (
    <header className="bg-nasa-gray p-4 shadow-lg flex justify-between items-center">
      <div className="flex items-center">
        <span className="text-2xl font-bold text-nasa-cyan animate-pulseGlow">🚀</span>
        <h1 className="text-2xl font-bold ml-3">Link Profiler Mission Control</h1>
      </div>
      <nav>
        {/* Navigation links can go here */}
        <ul className="flex space-x-4">
          <li><a href="#" className="hover:text-nasa-amber transition-colors">Overview</a></li>
          <li><a href="#" className="hover:text-nasa-amber transition-colors">Jobs</a></li>
          <li><a href="#" className="hover:text-nasa-amber transition-colors">Alerts</a></li>
          <li><a href="#" className="hover:text-nasa-amber transition-colors">Settings</a></li>
        </ul>
      </nav>
    </header>
  );
};

export default Header;
