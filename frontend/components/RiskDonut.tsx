
import React from 'react';
import { ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';
import { useTheme } from '../context/ThemeContext';

interface RiskDonutProps {
  score: number;
  size?: 'sm' | 'md';
}

/**
 * `box` is the size the class list already draws, in the pixels Recharts has to
 * be told: `w-20` is 5rem and `w-48` is 12rem at this app's 16px root, and the
 * two must agree or the first frame is the wrong size. See `initialDimension`
 * below for why it is passed at all -- Recharts 3 warns at `-1` in production
 * too, and `warn` is not stripped from the bundle.
 */
const SIZES = {
  sm: { container: 'w-20 h-20', box: 80, inner: 24, outer: 36, scoreText: 'text-lg', subText: 'text-[10px]' },
  md: { container: 'w-48 h-48 mx-auto', box: 192, inner: 60, outer: 80, scoreText: 'text-4xl', subText: 'text-sm' },
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
      {/* The box is fixed, so the initial measurement can be the real one: the
          donut draws at its final size on the first frame and Recharts never
          sees the `-1` it logs a warning about. */}
      <ResponsiveContainer
        width="100%"
        height="100%"
        initialDimension={{ width: s.box, height: s.box }}
      >
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