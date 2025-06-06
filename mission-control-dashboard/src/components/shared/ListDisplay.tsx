import React from 'react';

interface ListDisplayProps {
  title: string;
  items: string[];
  emptyMessage?: string;
  itemColorClass?: string; // Tailwind CSS class for item text color
  maxHeight?: string; // Tailwind CSS class for max height, e.g., 'max-h-40'
}

const ListDisplay: React.FC<ListDisplayProps> = ({
  title,
  items,
  emptyMessage = 'No data available.',
  itemColorClass = 'text-nasa-light-gray',
  maxHeight = 'max-h-40',
}) => {
  return (
    <>
      <h3 className="text-xl font-bold text-nasa-cyan mt-6 mb-3">{title}</h3>
      <div className={`${maxHeight} overflow-y-auto pr-2`}>
        {items.length > 0 ? (
          items.map((item, index) => (
            <p key={index} className={`text-sm mb-1 ${itemColorClass}`}>
              {item}
            </p>
          ))
        ) : (
          <p className="text-nasa-light-gray text-sm">{emptyMessage}</p>
        )}
      </div>
    </>
  );
};

export default ListDisplay;
