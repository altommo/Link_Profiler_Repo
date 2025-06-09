import React from 'react';

interface ChartContainerProps {
  title: string;
  children: React.ReactNode;
  className?: string;
}

const ChartContainer: React.FC<ChartContainerProps> = ({ title, children, className }) => {
  return (
    <div className={`bg-nasa-medium-blue p-6 rounded-lg shadow-lg border border-nasa-cyan ${className || ''}`}>
      <h3 className="text-xl font-bold text-nasa-cyan mb-4">{title}</h3>
      <div className="w-full h-64"> {/* Fixed height for charts */}
        {children}
      </div>
    </div>
  );
};

export default ChartContainer;
