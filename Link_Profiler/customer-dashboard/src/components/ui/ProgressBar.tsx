import React from 'react'; // Added React import

interface ProgressBarProps {
  percentage: number;
  colorClass?: string; // Tailwind CSS class for background color, e.g., 'bg-green-500'
  height?: string; // Tailwind CSS class for height, e.g., 'h-2.5'
}

const ProgressBar: React.FC<ProgressBarProps> = ({ percentage, colorClass = 'bg-nasa-cyan', height = 'h-2.5' }) => {
  const clampedPercentage = Math.max(0, Math.min(100, percentage));

  return (
    <div className={`w-full bg-gray-700 rounded-full ${height}`}>
      <div
        className={`${height} rounded-full ${colorClass}`}
        style={{ width: `${clampedPercentage}%` }}
      ></div>
    </div>
  );
};

export default ProgressBar;
