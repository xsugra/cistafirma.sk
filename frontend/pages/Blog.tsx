
import React from 'react';

// Mock Data for the blog
const ARTICLES = [
    {
        id: 1,
        title: "Zmeny v DPH od roku 2025: Na čo si dať pozor?",
        excerpt: "Prehľad najdôležitejších zmien v zákone o dani z pridanej hodnoty a ich dopad na B2B segment. Zistite, ako sa pripraviť na nové sadzby a vykazovanie.",
        category: "Legislatíva",
        date: "12. Február 2025",
        readTime: "5 min čítania",
        image: "fa-scale-balanced"
    },
    {
        id: 2,
        title: "Ako AI odhaľuje biele kone vo firmách",
        excerpt: "Náš nový model strojového učenia dokáže identifikovať podozrivé štruktúry s 95% presnosťou. Prečítajte si prípadovú štúdiu o odhalení daňového podvodu.",
        category: "Technológie",
        date: "10. Február 2025",
        readTime: "8 min čítania",
        image: "fa-microchip"
    },
    {
        id: 3,
        title: "Prečo je monitoring obchodných partnerov kľúčový?",
        excerpt: "Prevencia je lacnejšia ako vymáhanie pohľadávok. Ukážeme vám 3 signály, ktoré predpovedajú úpadok firmy mesiace vopred.",
        category: "Biznis",
        date: "5. Február 2025",
        readTime: "4 min čítania",
        image: "fa-chart-line"
    },
    {
        id: 4,
        title: "Novela obchodného zákonníka 2024",
        excerpt: "Aké nové povinnosti pribudli konateľom? Sumár zmien, ktoré ovplyvňujú ručenie štatutárov.",
        category: "Právo",
        date: "28. Január 2025",
        readTime: "6 min čítania",
        image: "fa-gavel"
    },
    {
        id: 5,
        title: "Digitalizácia účtovníctva: Budúcnosť bez papiera",
        excerpt: "Ako prejsť na plne digitálny obeh dokladov a ušetriť čas aj náklady. Tipy a triky pre slovenské s.r.o.",
        category: "Efektivita",
        date: "15. Január 2025",
        readTime: "5 min čítania",
        image: "fa-file-invoice"
    }
];

export const Blog: React.FC = () => {
    return (
        <div className="max-w-7xl mx-auto w-full animate-fade-in py-10">
            {/* Header */}
            <div className="text-center mb-12">
                <span className="text-blue-600 dark:text-blue-400 font-semibold tracking-wide uppercase text-sm">
                    Informačné centrum
                </span>
                <h1 className="text-3xl md:text-4xl font-bold text-gray-900 dark:text-white mt-3 mb-4">
                    Blog cistafirma.sk
                </h1>
                <p className="text-lg text-gray-600 dark:text-gray-400 max-w-2xl mx-auto">
                    Analýzy, legislatívne novinky a tipy pre bezpečnejšie podnikanie na Slovensku.
                </p>
            </div>

            {/* Featured Categories */}
            <div className="flex flex-wrap justify-center gap-3 mb-12">
                {['Všetky', 'Legislatíva', 'Technológie', 'Biznis', 'Právo'].map((cat, idx) => (
                    <button 
                        key={idx}
                        className={`px-4 py-2 rounded-full text-sm font-medium transition-colors ${idx === 0 
                            ? 'bg-blue-600 text-white' 
                            : 'bg-white dark:bg-slate-800 text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-slate-700 border border-gray-200 dark:border-slate-700'}`}
                    >
                        {cat}
                    </button>
                ))}
            </div>

            {/* Articles Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8 mb-16">
                {ARTICLES.map((article) => (
                    <div key={article.id} className="app-card group flex flex-col h-full hover:border-blue-300 dark:hover:border-blue-700 transition-colors duration-300">
                        <div className="h-48 bg-gradient-to-br from-gray-100 to-gray-200 dark:from-slate-800 dark:to-slate-900 flex items-center justify-center border-b border-gray-100 dark:border-slate-800 relative overflow-hidden">
                             {/* Abstract visual representation instead of real images */}
                             <div className="absolute inset-0 bg-blue-500/5 group-hover:bg-blue-500/10 transition-colors"></div>
                             <i className={`fas ${article.image} text-6xl text-gray-300 dark:text-slate-600 group-hover:scale-110 transition-transform duration-500`}></i>
                             
                             <div className="absolute top-4 left-4 bg-white dark:bg-slate-900 px-3 py-1 rounded-full text-xs font-bold text-blue-600 dark:text-blue-400 shadow-sm">
                                 {article.category}
                             </div>
                        </div>
                        
                        <div className="card-body flex flex-col flex-grow">
                            <div className="flex items-center gap-3 text-xs font-medium text-gray-500 dark:text-gray-400 mb-3">
                                <span><i className="far fa-calendar mr-1"></i>{article.date}</span>
                                <span>•</span>
                                <span><i className="far fa-clock mr-1"></i>{article.readTime}</span>
                            </div>
                            
                            <h3 className="text-xl font-bold text-gray-900 dark:text-white mb-3 group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors">
                                {article.title}
                            </h3>
                            
                            <p className="text-base text-gray-600 dark:text-gray-400 mb-6 flex-grow leading-relaxed">
                                {article.excerpt}
                            </p>
                            
                            <button className="text-blue-600 dark:text-blue-400 font-bold text-sm flex items-center gap-2 group/btn">
                                Čítať viac <i className="fas fa-arrow-right group-hover/btn:translate-x-1 transition-transform"></i>
                            </button>
                        </div>
                    </div>
                ))}
            </div>

            {/* Newsletter CTA */}
            <div className="app-card p-10 text-center relative overflow-hidden mb-12">
                 <div className="absolute inset-0 bg-gradient-to-r from-blue-600/10 to-purple-600/10 z-0"></div>
                 <div className="relative z-10 max-w-2xl mx-auto">
                     <i className="fas fa-envelope-open-text text-4xl text-blue-600 mb-4"></i>
                     <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">Nezmeškajte žiadne novinky</h2>
                     <p className="text-base text-gray-600 dark:text-gray-400 mb-6">
                         Prihláste sa na odber newslettra cistafirma.sk a dostávajte týždenný prehľad legislatívnych zmien priamo do mailu.
                     </p>
                     <div className="flex flex-col sm:flex-row gap-3 max-w-md mx-auto">
                         <input 
                            type="email" 
                            placeholder="Váš email" 
                            className="flex-grow px-4 py-3 rounded-lg border border-gray-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 outline-none"
                         />
                         <button className="btn btn-primary whitespace-nowrap">
                             Odoberať
                         </button>
                     </div>
                 </div>
            </div>
        </div>
    );
};
