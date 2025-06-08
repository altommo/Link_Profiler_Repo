import React from 'react'; // Added React import

interface MetricDisplayProps {
  label: string;
  value: string | number;
  valueColorClass?: string; // Tailwind CSS class for value color, e.g., 'text-nasa-amber'
  unit?: string; // Optional unit to display next to the value
}

const MetricDisplay: React.FC<MetricDisplayProps> = ({ label, value, valueColorClass = 'text-nasa-cyan', unit }) => {
  return (
    <div>
      <p className="text-nasa-light-gray text-lg">{label}:</p>
      <p className={`${valueColorClass} text-3xl`}>
        {value} {unit && <span className="text-base">{unit}</span>}
      </p>
    </div>
  );
};

export default MetricDisplay;
