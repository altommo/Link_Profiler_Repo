import React from 'react';

interface ProgressBarProps {
  percentage: number;
  colorClass?: string; // Tailwind CSS class for background color, e.g., 'bg-green-500'
  height?: string; // Tailwind CSS class for height, e.g., 'h-2.5'
  className?: string; // Added className prop
}

const ProgressBar: React.FC<ProgressBarProps> = ({ percentage, colorClass = 'bg-nasa-blue', height = 'h-2.5', className = '' }) => {
  return (
    <div className={`w-full bg-nasa-medium-blue rounded-full ${height} ${className}`}>
      <div
        className={`${colorClass} ${height} rounded-full transition-all duration-500 ease-out`}
        style={{ width: `${Math.max(0, Math.min(100, percentage))}%` }} // Ensure percentage is between 0 and 100
      ></div>
    </div>
  );
};

export default ProgressBar;
