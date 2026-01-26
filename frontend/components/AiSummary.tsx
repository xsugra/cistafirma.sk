
import React, { useState, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { InfoCard } from './InfoCard';
import { LoadingSpinner } from './LoadingSpinner';
import { generateRiskSummary } from '../services/geminiService';
import type { Company } from '../types';

interface AiSummaryProps {
    companyData: Company;
}

export const AiSummary: React.FC<AiSummaryProps> = ({ companyData }) => {
    const [summary, setSummary] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState<boolean>(false);
    const [error, setError] = useState<string | null>(null);

    const handleGenerateSummary = useCallback(async () => {
        setIsLoading(true);
        setError(null);
        try {
            const result = await generateRiskSummary(companyData);
            setSummary(result);
        } catch (e) {
            setError("Nepodarilo sa vygenerovať zhrnutie.");
            console.error(e);
        } finally {
            setIsLoading(false);
        }
    }, [companyData]);

    return (
        <InfoCard title="Gemini AI Analýza Rizík" icon="fa-robot">
            <div className="min-h-[100px]">
                {isLoading && <LoadingSpinner />}
                
                {error && !isLoading && (
                    <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4 text-center">
                        <p className="text-red-600 dark:text-red-300">{error}</p>
                    </div>
                )}
                
                {!isLoading && summary && (
                    <div className="prose prose-sm md:prose-base dark:prose-invert max-w-none">
                        <ReactMarkdown 
                            remarkPlugins={[remarkGfm]}
                            components={{
                                // Responsive Table Wrapper
                                table: ({node, ...props}) => (
                                    <div className="px-6 py-4 w-full overflow-x-auto my-6 rounded-xl border border-gray-200 dark:border-slate-700 shadow-sm bg-white dark:bg-slate-900">
                                        <table className="w-full border-collapse" {...props} />
                                    </div>
                                ),
                                thead: ({node, ...props}) => (
                                    <thead className="px-6 py-4 bg-gray-50 dark:bg-slate-800/80 border-b border-gray-200 dark:border-slate-700" {...props} />
                                ),
                                tbody: ({node, ...props}) => (
                                    <tbody className="divide-y divide-gray-100 dark:divide-slate-800" {...props} />
                                ),
                                th: ({node, ...props}) => (
                                    <th className="px-6 py-4 text-left text-xs font-bold text-gray-500 dark:text-gray-400 uppercase tracking-wider whitespace-nowrap" {...props} />
                                ),
                                td: ({node, ...props}) => (
                                    <td className="px-6 py-4 text-sm font-medium text-gray-900 dark:text-gray-100 whitespace-nowrap" {...props} />
                                ),
                                // Style links
                                a: ({node, ...props}) => <a className="text-blue-600 dark:text-blue-400 hover:underline font-medium" {...props} />,
                                // Style headers
                                h2: ({node, ...props}) => <h2 className="text-xl font-bold mt-8 mb-4 text-gray-900 dark:text-white flex items-center gap-2 border-b border-gray-100 dark:border-slate-800 pb-2" {...props} />,
                                h3: ({node, ...props}) => <h3 className="text-lg font-semibold mt-6 mb-3 text-gray-900 dark:text-white" {...props} />,
                                // Style lists
                                ul: ({node, ...props}) => <ul className="list-disc list-outside ml-5 space-y-2 my-4 text-gray-600 dark:text-gray-300" {...props} />,
                                li: ({node, ...props}) => <li className="pl-1 leading-relaxed" {...props} />,
                                // Style strong emphasis
                                strong: ({node, ...props}) => <strong className="font-bold text-gray-900 dark:text-white" {...props} />,
                                // Standard paragraph styling
                                p: ({node, ...props}) => <p className="leading-relaxed mb-4 text-gray-600 dark:text-gray-300" {...props} />,
                            }}
                        >
                            {summary}
                        </ReactMarkdown>
                    </div>
                )}

                {!isLoading && !summary && !error && (
                    <div className="text-center py-6">
                        <p className="mb-6 text-gray-500 dark:text-gray-400 max-w-lg mx-auto">
                            Získajte hĺbkovú analýzu rizík, finančného zdravia a prepojení v priebehu niekoľkých sekúnd pomocou umelej inteligencie.
                        </p>
                        <button 
                            onClick={handleGenerateSummary}
                            className="btn btn-primary px-8 py-3 rounded-full shadow-lg shadow-blue-500/20 hover:scale-105 transition-transform"
                        >
                            <i className="fas fa-magic mr-2"></i> Vygenerovať zhrnutie
                        </button>
                    </div>
                )}
            </div>
        </InfoCard>
    );
};
