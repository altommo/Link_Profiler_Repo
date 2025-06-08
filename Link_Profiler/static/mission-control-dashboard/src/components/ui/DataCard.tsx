import React from 'react';

interface DataCardProps {
  title: string;
  children: React.ReactNode;
  className?: string;
}

const DataCard: React.FC<DataCardProps> = ({ title, children, className }) => {
  return (
    <div className={`bg-nasa-gray p-6 rounded-lg shadow-lg border border-nasa-cyan ${className || ''}`}>
      <h2 className="text-2xl font-bold text-nasa-cyan mb-4">{title}</h2>
      {children}
    </div>
  );
};

export default DataCard;
