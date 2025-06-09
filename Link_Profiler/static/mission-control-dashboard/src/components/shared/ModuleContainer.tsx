import React from 'react';

interface ModuleContainerProps {
  title: string;
  children: React.ReactNode;
  className?: string;
}

const ModuleContainer: React.FC<ModuleContainerProps> = ({ title, children, className }) => {
  return (
    <div className={`bg-nasa-medium-blue p-6 rounded-lg shadow-lg border border-nasa-cyan ${className || ''}`}>
      <h2 className="text-2xl font-bold text-nasa-cyan mb-4">{title}</h2>
      {children}
    </div>
  );
};

export default ModuleContainer;
