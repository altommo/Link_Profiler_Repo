import React from 'react';

interface MetricDisplayProps {
  label: string;
  value: string | number | null | undefined; // Allow null or undefined
  valueColorClass?: string; // Tailwind CSS class for value color, e.g., 'text-nasa-amber'
  unit?: string; // Optional unit to display next to the value
}

const MetricDisplay: React.FC<MetricDisplayProps> = ({ label, value, valueColorClass = 'text-white', unit }) => {
  return (
    <div className="flex flex-col items-start">
      <span className="text-sm text-gray-400">{label}</span>
      <span className={`text-xl font-bold ${valueColorClass}`}>
        {value !== null && value !== undefined ? value : 'N/A'}
        {unit && value !== null && value !== undefined && <span className="ml-1 text-base font-normal">{unit}</span>}
      </span>
    </div>
  );
};

export default MetricDisplay;
