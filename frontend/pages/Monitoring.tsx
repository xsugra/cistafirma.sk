
import React, { useState, useCallback, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { SearchBar } from '../components/SearchBar';
import { CompanyDetail } from '../components/CompanyDetail';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { api } from '../api';
import type { Company } from '../types';

export const Monitoring: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const initialSearch = searchParams.get('ico') || '';
  const [query, setQuery] = useState<string>(initialSearch);
  const [companyData, setCompanyData] = useState<Company | null>(null);
  const [searchResults, setSearchResults] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [showIntro, setShowIntro] = useState<boolean>(true);

  const handleSearch = useCallback(async (searchQuery: string) => {
    const trimmedQuery = searchQuery.trim();
    if (!trimmedQuery || trimmedQuery.length < 2) {
      setError('Zadajte aspoň 2 znaky (IČO alebo názov).');
      return;
    }
    
    setIsLoading(true);
    setError(null);
    setCompanyData(null);
    setSearchResults([]);
    setShowIntro(false);
    setQuery(trimmedQuery);

    try {
        if (/^\d{8}$/.test(trimmedQuery)) {
            const data = await api.getCompany(trimmedQuery);
            setCompanyData(data);
            setSearchParams({ ico: trimmedQuery }, { replace: true });
        } else {
            const data = await api.searchCompanies(trimmedQuery);
            if (data.results && data.results.length === 1) {
                const detail = await api.getCompany(data.results[0].ico);
                setCompanyData(detail);
                setSearchParams({ ico: data.results[0].ico }, { replace: true });
            } else if (data.results && data.results.length > 1) {
                setSearchResults(data.results);
            } else {
                setError('Nenašli sa žiadne výsledky pre váš dopyt.');
            }
        }
    } catch (err: any) {
        setError(err.message || 'Nepodarilo sa načítať údaje o firme.');
    } finally {
        setIsLoading(false);
    }
  }, []);

  // Effect to handle initial search from navigation props
  useEffect(() => {
      if (initialSearch) {
          setQuery(initialSearch);
          handleSearch(initialSearch);
      }
  }, [initialSearch, handleSearch]);

  return (
    <div className="max-w-5xl mx-auto w-full animate-fade-in py-10">
        <div className="text-center mb-10">
            <h1 className="text-3xl md:text-4xl font-bold text-gray-900 dark:text-white mb-4">
                Monitoring a Analýza
            </h1>
            <p className="text-lg text-gray-600 dark:text-gray-400 max-w-2xl mx-auto">
                Zadajte IČO alebo názov spoločnosti a získajte okamžitý prístup k dátam.
            </p>
        </div>
        
        <div className="max-w-2xl mx-auto mb-12">
            <SearchBar onSearch={handleSearch} isLoading={isLoading} initialIco={query} />
        </div>
        
        <div className="min-h-[300px]">
            {isLoading && <LoadingSpinner />}
            
            {error && !isLoading && (
              <div className="text-center p-8 bg-white dark:bg-slate-900 rounded-xl border border-red-200 dark:border-red-900/50 shadow-lg">
                <i className="fas fa-exclamation-triangle text-red-500 text-3xl mb-4"></i>
                <p className="text-red-600 dark:text-red-400 font-medium">{error}</p>
              </div>
            )}

            {showIntro && !isLoading && !error && (
               <div className="text-center p-12">
                <div className="w-16 h-16 bg-blue-100 dark:bg-slate-800 rounded-full flex items-center justify-center mx-auto mb-6">
                    <i className="fas fa-search text-blue-600 dark:text-blue-400 text-2xl"></i>
                </div>
                <h3 className="text-xl font-bold text-gray-900 dark:text-white mb-3">Pripravený na analýzu?</h3>
                <p className="text-gray-600 dark:text-gray-400 text-base max-w-lg mx-auto">
                    Náš systém preveruje registre dlžníkov, finančnú správu a obchodný register v reálnom čase.
                </p>
                <div className="mt-8 inline-block bg-gray-50 dark:bg-slate-900 px-4 py-2 rounded-lg text-sm text-gray-500 dark:text-gray-400 border border-gray-200 dark:border-slate-800">
                    Tip: Skúste vyhľadať IČO 50059959 alebo názov firmy
                </div>
              </div>
            )}

            {searchResults.length > 0 && !companyData && !isLoading && (
                <div className="app-card overflow-hidden">
                    <div className="bg-gray-50 dark:bg-slate-900 px-6 py-4 border-b border-gray-100 dark:border-slate-800">
                        <h3 className="font-bold text-gray-900 dark:text-white">Výsledky vyhľadávania ({searchResults.length})</h3>
                    </div>
                    <div className="divide-y divide-gray-100 dark:divide-slate-800">
                        {searchResults.map(result => (
                            <div 
                                key={result.ico} 
                                onClick={() => handleSearch(result.ico)}
                                className="px-6 py-4 hover:bg-blue-50 dark:hover:bg-blue-900/20 cursor-pointer flex justify-between items-center group transition-colors"
                            >
                                <div>
                                    <h4 className="font-bold text-gray-900 dark:text-white group-hover:text-blue-600 dark:group-hover:text-blue-400">{result.nazov_UJ}</h4>
                                    <p className="text-sm text-gray-500">IČO: {result.ico} • {result.mesto}</p>
                                </div>
                                <i className="fas fa-chevron-right text-gray-300 group-hover:text-blue-500 transition-colors"></i>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {companyData && !isLoading && !error && (
              <CompanyDetail company={companyData} />
            )}
        </div>
    </div>
  );
};
