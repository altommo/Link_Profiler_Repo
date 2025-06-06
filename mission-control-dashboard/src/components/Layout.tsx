import React from 'react';
import Header from './Header';

interface LayoutProps {
  children: React.ReactNode;
}

const Layout: React.FC<LayoutProps> = ({ children }) => {
  return (
    <div className="flex flex-col min-h-screen bg-nasa-blue text-nasa-cyan font-mono">
      <Header />
      <main className="flex-grow p-8">
        <div className="container mx-auto">
          {children}
        </div>
      </main>
      {/* Optional: Footer component can go here */}
    </div>
  );
};

export default Layout;
