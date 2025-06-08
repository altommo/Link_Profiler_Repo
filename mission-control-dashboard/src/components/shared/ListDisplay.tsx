import React from 'react';

interface ListDisplayProps {
  title: string;
  items: string[];
  emptyMessage?: string;
  // itemColorClass can now be a string (Tailwind class) or a function that returns a string
  itemColorClass?: string | ((item: string) => string);
  maxHeight?: string; // Tailwind CSS class for max height, e.g., 'max-h-40'
}

const ListDisplay: React.FC<ListDisplayProps> = ({
  title,
  items,
  emptyMessage = 'No items to display.',
  itemColorClass,
  maxHeight = 'max-h-64', // Default max height
}) => {
  return (
    <div className="bg-gray-800 p-4 rounded-lg shadow-md">
      <h3 className="text-lg font-semibold text-white mb-2">{title}</h3>
      <div className={`overflow-y-auto ${maxHeight}`}>
        {items.length > 0 ? (
          <ul className="list-disc list-inside text-gray-300">
            {items.map((item, index) => (
              <li key={index} className={typeof itemColorClass === 'function' ? itemColorClass(item) : itemColorClass || ''}>
                {item}
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-gray-400">{emptyMessage}</p>
        )}
      </div>
    </div>
  );
};

export default ListDisplay;
