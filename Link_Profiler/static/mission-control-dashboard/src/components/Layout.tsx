import React, { useState, ReactNode } from 'react';
import Header from './layout/Header'; // Corrected import path
import Sidebar from './layout/Sidebar'; // Corrected import path
import useRealTimeData from '../../hooks/useRealTimeData'; // Initialize WebSocket at layout level

interface LayoutProps {
  children: ReactNode;
}

const Layout: React.FC<LayoutProps> = ({ children }) => {
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  
  // Initialize WebSocket connection once at the layout level
  useRealTimeData();

  const toggleSidebar = () => {
    setIsSidebarOpen(!isSidebarOpen);
  };

  return (
    <div className="flex flex-col min-h-screen bg-nasa-dark-blue text-nasa-light-gray">
      {/* Mobile Header */}
      <Header toggleSidebar={toggleSidebar} />

      <div className="flex flex-1">
        {/* Sidebar */}
        <Sidebar isOpen={isSidebarOpen} toggleSidebar={toggleSidebar} />

        {/* Main Content Area */}
        <main className="flex-1 p-6 md:p-8 overflow-y-auto">
          {children}
        </main>
      </div>
    </div>
  );
};

export default Layout;
