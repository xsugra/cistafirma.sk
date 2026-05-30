
import React from 'react';
import { ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';
import { useTheme } from '../context/ThemeContext';

interface RiskDonutProps {
  score: number;
  size?: 'sm' | 'md';
}

const SIZES = {
  sm: { container: 'w-20 h-20', inner: 24, outer: 36, scoreText: 'text-lg', subText: 'text-[10px]' },
  md: { container: 'w-48 h-48 mx-auto', inner: 60, outer: 80, scoreText: 'text-4xl', subText: 'text-sm' },
};

export const RiskDonut: React.FC<RiskDonutProps> = ({ score, size = 'md' }) => {
  const { isDark } = useTheme();
  const data = [
    { name: 'Score', value: score },
    { name: 'Remaining', value: 100 - score },
  ];

  const getColor = (value: number) => {
    if (value > 75) return '#4ade80';
    if (value > 50) return '#facc15';
    return '#f87171';
  };

  const color = getColor(score);
  const COLORS = [color, isDark ? '#1e293b' : '#e2e8f0'];
  const s = SIZES[size];

  return (
    <div className={`relative ${s.container}`}>
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={data}
            cx="50%"
            cy="50%"
            innerRadius={s.inner}
            outerRadius={s.outer}
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
        <span className={`${s.scoreText} font-bold`} style={{ color }}>{score}</span>
        {size === 'md' && <span className={`${s.subText} text-gray-400`}>/ 100</span>}
      </div>
    </div>
  );
};