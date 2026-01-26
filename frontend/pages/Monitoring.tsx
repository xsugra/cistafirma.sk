
import React, { useState, useCallback, useEffect } from 'react';
import { SearchBar } from '../components/SearchBar';
import { CompanyDetail } from '../components/CompanyDetail';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { api } from '../api';
import type { Company } from '../types';

interface MonitoringProps {
    initialSearch?: string;
}

export const Monitoring: React.FC<MonitoringProps> = ({ initialSearch }) => {
  const [ico, setIco] = useState<string>(initialSearch || '');
  const [companyData, setCompanyData] = useState<Company | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [showIntro, setShowIntro] = useState<boolean>(true);

  const handleSearch = useCallback(async (searchIco: string) => {
    if (!searchIco || searchIco.length !== 8) {
      setError('Zadajte platné IČO (8 číslic).');
      return;
    }
    
    setIsLoading(true);
    setError(null);
    setCompanyData(null);
    setShowIntro(false);
    setIco(searchIco);

    try {
        const data = await api.getCompany(searchIco);
        setCompanyData(data);
    } catch (err: any) {
        setError(err.message || 'Nepodarilo sa načítať údaje o firme.');
    } finally {
        setIsLoading(false);
    }
  }, []);

  // Effect to handle initial search from navigation props
  useEffect(() => {
      if (initialSearch) {
          setIco(initialSearch);
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
                Zadajte IČO a získajte okamžitý prístup k finančným a právnym dátam.
            </p>
        </div>
        
        <div className="max-w-2xl mx-auto mb-12">
            <SearchBar onSearch={handleSearch} isLoading={isLoading} initialIco={ico} />
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
                    Tip: Skúste vyhľadať IČO 50059959
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
