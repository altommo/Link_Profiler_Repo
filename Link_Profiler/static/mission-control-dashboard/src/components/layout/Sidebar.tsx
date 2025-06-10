import React from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';

interface SidebarProps {
  isOpen: boolean;
  toggleSidebar: () => void;
}

const Sidebar: React.FC<SidebarProps> = ({ isOpen, toggleSidebar }) => {
  const { isAdmin } = useAuth();

  return (
    <>
      {/* Overlay */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black bg-opacity-50 z-40 lg:hidden"
          onClick={toggleSidebar}
        ></div>
      )}

      {/* Sidebar */}
      <aside
        className={`fixed inset-y-0 left-0 transform ${isOpen ? 'translate-x-0' : '-translate-x-full'
          } lg:translate-x-0 transition-transform duration-300 ease-in-out bg-nasa-medium-blue text-nasa-light-gray w-64 p-4 z-50 shadow-lg border-r border-nasa-cyan`}
      >
        <div className="flex justify-between items-center mb-6">
          <h2 className="text-xl font-semibold text-nasa-cyan">Navigation</h2>
          <button onClick={toggleSidebar} className="text-nasa-light-gray focus:outline-none lg:hidden">
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12"></path>
            </svg>
          </button>
        </div>
        <nav>
          <ul>
            <li className="mb-3">
              <Link to="/" className="nav-link" onClick={toggleSidebar}>
                Overview
              </Link>
            </li>
            <li className="mb-3">
              <Link to="/dashboard" className="nav-link" onClick={toggleSidebar}>
                Dashboard
              </Link>
            </li>
            <li className="mb-3">
              <Link to="/jobs" className="nav-link" onClick={toggleSidebar}>
                Job Management
              </Link>
            </li>
            {isAdmin && (
              <li className="mb-3">
                <Link to="/settings" className="nav-link" onClick={toggleSidebar}>
                  Settings
                </Link>
              </li>
            )}
          </ul>
        </nav>
      </aside>
    </>
  );
};

export default Sidebar;
