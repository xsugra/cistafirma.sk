
import React from 'react';

interface StatusBadgeProps {
  status: 'Aktívna' | 'V likvidácii' | 'V konkurze' | 'Vymazaná';
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status }) => {
  const getStatusColor = () => {
    switch (status) {
      case 'Aktívna':
        return 'bg-green-500/20 text-green-300 border-green-500/30';
      case 'V likvidácii':
        return 'bg-yellow-500/20 text-yellow-300 border-yellow-500/30';
      case 'V konkurze':
        return 'bg-red-500/20 text-red-300 border-red-500/30';
      case 'Vymazaná':
        return 'bg-gray-600/20 text-gray-400 border-gray-600/30';
      default:
        return 'bg-gray-600/20 text-gray-400 border-gray-600/30';
    }
  };

  return (
    <span className={`px-3 py-1 text-sm font-semibold rounded-full border ${getStatusColor()}`}>
      {status}
    </span>
  );
};
