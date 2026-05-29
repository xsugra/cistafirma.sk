import React from 'react';

export const DetailItem: React.FC<{ label: string; value: React.ReactNode; icon: string }> = ({ label, value, icon }) => (
    <div className="flex items-start space-x-3">
        <i className={`fas ${icon} text-blue-500 dark:text-blue-400 mt-1 w-4 text-center`}></i>
        <div>
            <p className="text-sm text-gray-500 dark:text-gray-400">{label}</p>
            <p className="font-semibold text-gray-900 dark:text-white">{value}</p>
        </div>
    </div>
);
