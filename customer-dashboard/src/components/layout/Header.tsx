import React from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth'; // Adjust path as necessary

interface HeaderProps {
  toggleSidebar: () => void;
}

const Header: React.FC<HeaderProps> = ({ toggleSidebar }) => {
  const { user, logout } = useAuth();

  return (
    <header className="bg-nasa-medium-blue p-4 flex justify-between items-center shadow-lg md:hidden">
      <div className="flex items-center">
        <button onClick={toggleSidebar} className="text-nasa-cyan text-2xl mr-4 focus:outline-none">
          <i className="fas fa-bars"></i> {/* FontAwesome bars icon for mobile menu */}
        </button>
        <Link to="/dashboard" className="text-nasa-cyan text-2xl font-bold"> {/* Changed to /dashboard */}
          Link Profiler
        </Link>
      </div>
      <div className="flex items-center space-x-4">
        {user && (
          <span className="text-nasa-light-gray text-sm hidden sm:inline">
            Welcome, {user.username} {user.is_admin && '(Admin)'}
          </span>
        )}
        <button onClick={logout} className="btn-secondary btn-xs">
          Logout
        </button>
      </div>
    </header>
  );
};

export default Header;
