
import React from 'react';

interface InfoCardProps {
  title: string;
  icon: string;
  children: React.ReactNode;
}

export const InfoCard: React.FC<InfoCardProps> = ({ title, icon, children }) => {
  return (
    <div className="bg-light-card dark:bg-dark-card rounded-xl border border-light-border dark:border-dark-border shadow-lg dark:shadow-none overflow-hidden transition-all duration-300">
      <div className="px-6 py-4 bg-gray-50/50 dark:bg-slate-900/50 border-b border-light-border dark:border-dark-border">
        <h3 className="text-lg font-bold text-light-text dark:text-white flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-brand/10 flex items-center justify-center">
            <i className={`fas ${icon} text-brand`}></i>
          </div>
          {title}
        </h3>
      </div>
      <div className="p-6">
        {children}
      </div>
    </div>
  );
};
