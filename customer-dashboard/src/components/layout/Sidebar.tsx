import React from 'react';
import { NavLink } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth'; // Adjust path as necessary

interface SidebarProps {
  isOpen: boolean;
  toggleSidebar: () => void;
}

const Sidebar: React.FC<SidebarProps> = ({ isOpen, toggleSidebar }) => {
  const { isAdmin } = useAuth();

  return (
    <>
      {/* Overlay for mobile */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black bg-opacity-50 z-40 md:hidden"
          onClick={toggleSidebar}
        ></div>
      )}

      <aside
        className={`fixed inset-y-0 left-0 transform ${
          isOpen ? 'translate-x-0' : '-translate-x-full'
        } md:translate-x-0 transition-transform duration-300 ease-in-out
        bg-nasa-medium-blue w-64 p-6 shadow-xl z-50 md:relative md:flex-shrink-0`}
      >
        <div className="flex justify-between items-center mb-8">
          <h2 className="text-nasa-cyan text-3xl font-bold">
            <i className="fas fa-rocket mr-2"></i>MC
          </h2>
          <button onClick={toggleSidebar} className="text-nasa-cyan text-2xl md:hidden focus:outline-none">
            <i className="fas fa-times"></i> {/* Close icon for mobile */}
          </button>
        </div>

        <nav className="space-y-4">
          <NavLink
            to="/overview"
            className={({ isActive }) =>
              `nav-link ${isActive ? 'nav-link-active' : ''}`
            }
            onClick={isOpen ? toggleSidebar : undefined} // Close sidebar on link click in mobile
          >
            <i className="fas fa-tachometer-alt mr-3"></i>Overview
          </NavLink>
          <NavLink
            to="/jobs"
            className={({ isActive }) =>
              `nav-link ${isActive ? 'nav-link-active' : ''}`
            }
            onClick={isOpen ? toggleSidebar : undefined}
          >
            <i className="fas fa-tasks mr-3"></i>Jobs
          </NavLink>
          <NavLink
            to="/alerts"
            className={({ isActive }) =>
              `nav-link ${isActive ? 'nav-link-active' : ''}`
            }
            onClick={isOpen ? toggleSidebar : undefined}
          >
            <i className="fas fa-bell mr-3"></i>Alerts
          </NavLink>
          {isAdmin && (
            <NavLink
              to="/settings"
              className={({ isActive }) =>
                `nav-link ${isActive ? 'nav-link-active' : ''}`
              }
              onClick={isOpen ? toggleSidebar : undefined}
            >
              <i className="fas fa-cogs mr-3"></i>Settings
            </NavLink>
          )}
        </nav>
      </aside>
    </>
  );
};

export default Sidebar;
