
import React from 'react';
import { ResponsiveContainer, BarChart, XAxis, YAxis, Tooltip, Legend, Bar, CartesianGrid } from 'recharts';
import type { Financials } from '../types';

interface FinancialChartProps {
  data: Financials[];
}

export const FinancialChart: React.FC<FinancialChartProps> = ({ data }) => {
    const formatCurrency = (value: number) => {
        if (value >= 1000000) return `${(value / 1000000).toFixed(1)}M €`;
        if (value >= 1000) return `${(value / 1000).toFixed(0)}k €`;
        return `${value} €`;
    }

  return (
    <div style={{ width: '100%', height: 300 }}>
      <ResponsiveContainer>
        <BarChart data={data} margin={{ top: 5, right: 20, left: 30, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
          <XAxis dataKey="year" stroke="#9ca3af" />
          <YAxis stroke="#9ca3af" tickFormatter={formatCurrency}/>
          <Tooltip 
            contentStyle={{ backgroundColor: '#0f172a', border: '1px solid #1e293b', color: '#e5e7eb' }} 
            formatter={(value: number) => [value.toLocaleString('sk-SK', {style: 'currency', currency: 'EUR'}), '']}
            />
          <Legend wrapperStyle={{color: '#e5e7eb'}} />
          <Bar dataKey="revenue" fill="#60a5fa" name="Tržby" />
          <Bar dataKey="profit" fill="#818cf8" name="Zisk" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
};