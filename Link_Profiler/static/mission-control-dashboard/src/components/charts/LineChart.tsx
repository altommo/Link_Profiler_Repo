import React from 'react';
import {
  LineChart as RechartsLineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';

interface LineChartProps {
  data: any[];
  dataKey: string; // Key for the x-axis (e.g., 'name', 'timestamp')
  lineKeys: { key: string; stroke: string; name?: string }[]; // Array of objects for lines
  tooltipLabelFormatter?: (value: string | number) => string;
  tooltipValueFormatter?: (value: string | number, name: string, props: any) => [string | number, string];
  xAxisTickFormatter?: (value: string | number) => string;
  yAxisTickFormatter?: (value: string | number) => string;
}

const LineChart: React.FC<LineChartProps> = ({
  data,
  dataKey,
  lineKeys,
  tooltipLabelFormatter,
  tooltipValueFormatter,
  xAxisTickFormatter,
  yAxisTickFormatter,
}) => {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <RechartsLineChart
        data={data}
        margin={{
          top: 5,
          right: 30,
          left: 20,
          bottom: 5,
        }}
      >
        <CartesianGrid strokeDasharray="3 3" stroke="theme('colors.nasa-medium-blue')" />
        <XAxis dataKey={dataKey} stroke="theme('colors.nasa-cyan')" tickFormatter={xAxisTickFormatter} />
        <YAxis stroke="theme('colors.nasa-cyan')" tickFormatter={yAxisTickFormatter} />
        <Tooltip
          contentStyle={{ backgroundColor: 'theme('colors.nasa-dark-blue')', border: '1px solid theme('colors.nasa-cyan')', color: 'theme('colors.nasa-cyan')' }}
          labelStyle={{ color: 'theme('colors.nasa-amber')' }}
          itemStyle={{ color: 'theme('colors.nasa-cyan')' }}
          labelFormatter={tooltipLabelFormatter}
          formatter={tooltipValueFormatter}
        />
        <Legend wrapperStyle={{ color: 'theme('colors.nasa-cyan')' }} />
        {lineKeys.map((line, index) => (
          <Line
            key={index}
            type="monotone"
            dataKey={line.key}
            stroke={line.stroke}
            name={line.name || line.key}
            activeDot={{ r: 8 }}
            strokeWidth={2}
          />
        ))}
      </RechartsLineChart>
    </ResponsiveContainer>
  );
};

export default LineChart;
