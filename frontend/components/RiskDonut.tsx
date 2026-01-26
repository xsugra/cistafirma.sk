
import React from 'react';
import { ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';

interface RiskDonutProps {
  score: number;
}

export const RiskDonut: React.FC<RiskDonutProps> = ({ score }) => {
  const data = [
    { name: 'Score', value: score },
    { name: 'Remaining', value: 100 - score },
  ];

  const getColor = (value: number) => {
    if (value > 75) return '#4ade80'; // green
    if (value > 50) return '#facc15'; // yellow
    return '#f87171'; // red
  };

  const color = getColor(score);
  const COLORS = [color, '#1e293b']; // Use darker slate color for the remaining part

  return (
    <div className="relative w-48 h-48 mx-auto">
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={data}
            cx="50%"
            cy="50%"
            innerRadius={60}
            outerRadius={80}
            startAngle={90}
            endAngle={450}
            paddingAngle={0}
            dataKey="value"
          >
            {data.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} stroke={COLORS[index % COLORS.length]}/>
            ))}
          </Pie>
        </PieChart>
      </ResponsiveContainer>
      <div className="absolute inset-0 flex items-center justify-center flex-col">
        <span className="text-4xl font-bold" style={{ color }}>{score}</span>
        <span className="text-sm text-gray-400">/ 100</span>
      </div>
    </div>
  );
};