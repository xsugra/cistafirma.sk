
import React, { useState, useEffect, useRef } from 'react';
import { api } from '../api';

interface SearchBarProps {
  onSearch: (query: string) => void;
  isLoading: boolean;
  initialIco: string;
}

export const SearchBar: React.FC<SearchBarProps> = ({ onSearch, isLoading, initialIco }) => {
  const [query, setQuery] = useState(initialIco);
  const [suggestions, setSuggestions] = useState<any[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [isSearching, setIsSearching] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const isFocused = useRef(false);

  useEffect(() => {
    setQuery(initialIco);
  }, [initialIco]);

  // Handle click outside to close suggestions
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setShowSuggestions(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Autocomplete logic with debounce
  useEffect(() => {
    const fetchSuggestions = async () => {
      const trimmedQuery = query.trim();
      if (trimmedQuery.length < 2) {
        setSuggestions([]);
        return;
      }

      setIsSearching(true);
      try {
        const data = await api.searchCompanies(trimmedQuery);
        setSuggestions(data.results || []);
        if (isFocused.current) setShowSuggestions(true);
      } catch (e) {
        console.error("Autocomplete error", e);
      } finally {
        setIsSearching(false);
      }
    };

    const timer = setTimeout(fetchSuggestions, 300);
    return () => clearTimeout(timer);
  }, [query]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmedQuery = query.trim();
    setShowSuggestions(false);
    onSearch(trimmedQuery);
  };

  const handleSelectSuggestion = (item: any) => {
    setQuery(item.ico);
    setShowSuggestions(false);
    onSearch(item.ico);
  };

  return (
    <div className="relative w-full px-4 sm:px-0" ref={dropdownRef}>
      <form onSubmit={handleSubmit}>
        <div className="flex items-center bg-white dark:bg-slate-900 border-2 border-gray-200 dark:border-slate-800 rounded-full shadow-lg overflow-hidden focus-within:border-blue-500 focus-within:ring-2 focus-within:ring-blue-200 dark:focus-within:ring-blue-900 transition-all duration-300">
          <i className="fas fa-search text-gray-400 pl-4 sm:pl-6 pr-2 sm:pr-3 text-lg sm:text-xl"></i>
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onFocus={() => { isFocused.current = true; if (query.length >= 2 && suggestions.length > 0) setShowSuggestions(true); }}
            onBlur={() => { isFocused.current = false; }}
            placeholder="Zadajte IČO alebo názov firmy..."
            className="w-full bg-transparent text-base sm:text-lg text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500 py-3 sm:py-4 pr-24 sm:pr-36 outline-none"
            disabled={isLoading}
          />
          <button
            type="submit"
            className="absolute right-1.5 sm:right-2 top-1/2 -translate-y-1/2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white font-semibold py-2 sm:py-3 px-4 sm:px-8 rounded-full transition-transform hover:scale-105 active:scale-95 shadow-md text-sm sm:text-base"
            disabled={isLoading}
          >
            {isLoading || isSearching ? <i className="fas fa-circle-notch animate-spin"></i> : 'Overiť'}
          </button>
        </div>
      </form>

      {/* Suggestions Dropdown */}
      {showSuggestions && suggestions.length > 0 && (
        <div className="absolute left-0 right-0 mt-2 mx-4 sm:mx-0 bg-white dark:bg-slate-900 border border-gray-200 dark:border-slate-800 rounded-2xl shadow-2xl overflow-hidden z-[100] animate-fade-in">
          <div className="max-h-[300px] overflow-y-auto">
            {suggestions.map((item) => (
              <div
                key={item.ico}
                onClick={() => handleSelectSuggestion(item)}
                className="px-6 py-3 hover:bg-blue-50 dark:hover:bg-blue-900/20 cursor-pointer flex justify-between items-center group transition-colors border-b border-gray-50 dark:border-slate-800/50 last:border-0"
              >
                <div className="flex-grow min-w-0 mr-4">
                  <p className="font-bold text-gray-900 dark:text-white truncate group-hover:text-blue-600 dark:group-hover:text-blue-400">
                    {item.nazov_UJ}
                  </p>
                  <p className="text-xs text-gray-500 flex gap-2">
                    <span className="font-mono">IČO: {item.ico}</span>
                    <span>•</span>
                    <span className="truncate">{item.mesto}</span>
                  </p>
                </div>
                <div className="flex-shrink-0">
                   <span className="text-[10px] px-2 py-0.5 rounded bg-gray-100 dark:bg-slate-800 text-gray-500 uppercase font-bold">
                     {item.legal_form_short || 'Firma'}
                   </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
