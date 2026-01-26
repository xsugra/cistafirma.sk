
import React, { useState, useEffect } from 'react';

interface SearchBarProps {
  onSearch: (ico: string) => void;
  isLoading: boolean;
  initialIco: string;
}

export const SearchBar: React.FC<SearchBarProps> = ({ onSearch, isLoading, initialIco }) => {
  const [ico, setIco] = useState(initialIco);

  useEffect(() => {
    setIco(initialIco);
  }, [initialIco]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSearch(ico);
  };

  return (
    <form onSubmit={handleSubmit} className="relative w-full px-4 sm:px-0">
      <div className="flex items-center bg-white dark:bg-slate-900 border-2 border-gray-200 dark:border-slate-800 rounded-full shadow-lg overflow-hidden focus-within:border-blue-500 focus-within:ring-2 focus-within:ring-blue-200 dark:focus-within:ring-blue-900 transition-all duration-300">
        <i className="fas fa-search text-gray-400 pl-4 sm:pl-6 pr-2 sm:pr-3 text-lg sm:text-xl"></i>
        <input
          type="text"
          value={ico}
          onChange={(e) => setIco(e.target.value)}
          placeholder="Zadajte IČO spoločnosti..."
          className="w-full bg-transparent text-base sm:text-lg text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500 py-3 sm:py-4 pr-24 sm:pr-36 outline-none"
          disabled={isLoading}
        />
        <button
          type="submit"
          className="absolute right-1.5 sm:right-2 top-1/2 -translate-y-1/2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white font-semibold py-2 sm:py-3 px-4 sm:px-8 rounded-full transition-transform hover:scale-105 active:scale-95 shadow-md text-sm sm:text-base"
          disabled={isLoading}
        >
          {isLoading ? <span className="animate-pulse">...</span> : 'Overiť'}
        </button>
      </div>
    </form>
  );
};
