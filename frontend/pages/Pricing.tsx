
import React from 'react';
import { PRICING_PLANS } from '../constants';

export const Pricing: React.FC = () => {
    return (
        <div className="max-w-7xl mx-auto w-full py-10 animate-fade-in">
            <div className="text-center mb-16">
                <h1 className="text-3xl md:text-4xl font-bold text-gray-900 dark:text-white mb-4">
                    Vyberte si plán na mieru
                </h1>
                <p className="text-lg text-gray-600 dark:text-gray-400">
                    Transparentné ceny pre každú veľkosť podnikania.
                </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8">
                {PRICING_PLANS.map((plan) => (
                    <div 
                        key={plan.id} 
                        className={`relative flex flex-col p-6 rounded-2xl transition-transform duration-300 hover:-translate-y-2
                        ${plan.isPopular 
                            ? 'bg-blue-600 text-white shadow-xl shadow-blue-500/20 scale-105 z-10' 
                            : 'bg-white dark:bg-slate-900 border border-gray-200 dark:border-slate-800 text-gray-900 dark:text-gray-100 shadow-lg'
                        }`}
                    >
                        {plan.isPopular && (
                            <div className="absolute top-0 right-0 bg-yellow-400 text-yellow-900 text-xs font-bold px-3 py-1 rounded-bl-lg rounded-tr-lg">
                                ODPORÚČANÉ
                            </div>
                        )}
                        
                        <h3 className={`text-xl font-bold mb-2 ${plan.isPopular ? 'text-white' : 'text-gray-900 dark:text-white'}`}>
                            {plan.name}
                        </h3>
                        
                        <div className="mb-6">
                            <span className="text-4xl font-bold">{plan.price}€</span>
                            <span className={`text-sm ${plan.isPopular ? 'text-blue-100' : 'text-gray-500 dark:text-gray-400'}`}>/ mesačne</span>
                        </div>

                        <ul className="space-y-4 mb-8 flex-grow">
                            {plan.features.map((feature, idx) => (
                                <li key={idx} className="flex items-start gap-3 text-sm">
                                    <i className={`fas fa-check mt-1 ${plan.isPopular ? 'text-blue-200' : 'text-blue-500'}`}></i>
                                    <span className={plan.isPopular ? 'text-blue-50' : 'text-gray-600 dark:text-gray-300'}>
                                        {feature}
                                    </span>
                                </li>
                            ))}
                        </ul>

                        <button className={`w-full py-3 px-6 rounded-lg font-semibold transition-colors 
                            ${plan.isPopular 
                                ? 'bg-white text-blue-600 hover:bg-gray-100' 
                                : 'bg-gray-900 dark:bg-slate-800 text-white hover:bg-gray-800 dark:hover:bg-slate-700'
                            }`}
                        >
                            {plan.buttonText}
                        </button>
                    </div>
                ))}
            </div>
        </div>
    );
};
