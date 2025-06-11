import React, { useState } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { Bell, Search, User, Settings, LogOut, ChevronDown } from 'lucide-react';

const Header: React.FC = () => {
  const { user, logout } = useAuth();
  const [isProfileMenuOpen, setIsProfileMenuOpen] = useState(false);
  const [notifications] = useState(3); // Mock notification count

  const handleLogout = () => {
    logout();
    setIsProfileMenuOpen(false);
  };

  return (
    <header className="bg-white border-b border-neutral-200 sticky top-0 z-50">
      <div className="px-6 py-4">
        <div className="flex items-center justify-between">
          {/* Logo and Title */}
          <div className="flex items-center space-x-4">
            <div className="text-xl font-bold text-brand-primary">
              Link Profiler
            </div>
            <div className="hidden md:block text-sm text-neutral-500">
              Customer Dashboard
            </div>
          </div>

          {/* Search Bar */}
          <div className="hidden lg:flex flex-1 max-w-lg mx-8">
            <div className="relative w-full">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                <Search className="h-5 w-5 text-neutral-400" />
              </div>
              <input
                type="text"
                className="block w-full pl-10 pr-3 py-2 border border-neutral-300 rounded-lg leading-5 bg-white placeholder-neutral-500 focus:outline-none focus:placeholder-neutral-400 focus:ring-1 focus:ring-brand-primary focus:border-brand-primary"
                placeholder="Search domains, jobs, reports..."
              />
            </div>
          </div>

          {/* Right Side Actions */}
          <div className="flex items-center space-x-4">
            {/* Notifications */}
            <button className="relative p-2 text-neutral-400 hover:text-neutral-600 transition-colors">
              <Bell className="h-6 w-6" />
              {notifications > 0 && (
                <span className="absolute top-0 right-0 inline-flex items-center justify-center px-2 py-1 text-xs font-bold leading-none text-white transform translate-x-1/2 -translate-y-1/2 bg-error rounded-full">
                  {notifications}
                </span>
              )}
            </button>

            {/* Profile Dropdown */}
            <div className="relative">
              <button
                onClick={() => setIsProfileMenuOpen(!isProfileMenuOpen)}
                className="flex items-center space-x-3 p-2 text-neutral-700 hover:text-neutral-900 transition-colors focus:outline-none focus:ring-2 focus:ring-brand-primary rounded-lg"
              >
                <div className="flex items-center space-x-2">
                  <div className="w-8 h-8 bg-brand-primary rounded-full flex items-center justify-center">
                    <User className="h-5 w-5 text-white" />
                  </div>
                  <div className="hidden md:block text-left">
                    <div className="text-sm font-medium">{user?.username}</div>
                    <div className="text-xs text-neutral-500 capitalize">{user?.role}</div>
                  </div>
                </div>
                <ChevronDown className="h-4 w-4 text-neutral-400" />
              </button>

              {/* Dropdown Menu */}
              {isProfileMenuOpen && (
                <div className="absolute right-0 mt-2 w-48 bg-white rounded-lg shadow-lg border border-neutral-200 py-1 z-50">
                  <div className="px-4 py-2 border-b border-neutral-200">
                    <div className="text-sm font-medium text-neutral-900">{user?.username}</div>
                    <div className="text-xs text-neutral-500">{user?.email}</div>
                  </div>
                  
                  <a
                    href="/profile"
                    className="flex items-center px-4 py-2 text-sm text-neutral-700 hover:bg-neutral-50 transition-colors"
                  >
                    <User className="h-4 w-4 mr-3" />
                    Profile Settings
                  </a>
                  
                  <a
                    href="/profile#preferences"
                    className="flex items-center px-4 py-2 text-sm text-neutral-700 hover:bg-neutral-50 transition-colors"
                  >
                    <Settings className="h-4 w-4 mr-3" />
                    Preferences
                  </a>
                  
                  <div className="border-t border-neutral-200 my-1"></div>
                  
                  <button
                    onClick={handleLogout}
                    className="flex items-center w-full px-4 py-2 text-sm text-error hover:bg-red-50 transition-colors"
                  >
                    <LogOut className="h-4 w-4 mr-3" />
                    Sign Out
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </header>
  );
};

export default Header;
