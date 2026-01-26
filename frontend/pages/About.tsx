
import React from 'react';

export const About: React.FC = () => {
    return (
        <div className="max-w-4xl mx-auto w-full animate-fade-in py-10">
            <div className="text-center mb-12">
                <h1 className="text-3xl md:text-4xl font-bold text-gray-900 dark:text-white mb-6">
                    O projekte cistafirma.sk
                </h1>
                <p className="text-lg text-gray-600 dark:text-gray-400">
                    Transparentnosť, dáta a umelá inteligencia v službách bezpečného podnikania.
                </p>
            </div>

            <div className="space-y-12">
                {/* Vision Section */}
                <div className="app-card p-8 md:p-10">
                    <div className="flex flex-col md:flex-row gap-8 items-center">
                        <div className="flex-1">
                            <h2 className="text-2xl md:text-3xl font-bold text-gray-900 dark:text-white mb-4">Naša misia</h2>
                            <p className="text-base text-gray-600 dark:text-gray-300 leading-relaxed mb-4">
                                Projekt <strong>cistafirma.sk</strong> vznikol z jednoduchej potreby: mať rýchly, prehľadný a spoľahlivý nástroj na overovanie obchodných partnerov. V dobe, kedy sa ekonomika zrýchľuje, nemôžu podnikatelia strácať hodiny manuálnym prehľadávaním desiatok registrov.
                            </p>
                            <p className="text-base text-gray-600 dark:text-gray-300 leading-relaxed">
                                Veríme, že transparentnosť je základom zdravého podnikateľského prostredia. Našim cieľom je poskytnúť každému podnikateľovi – od živnostníkov po veľké korporácie – nástroje, ktoré odhalia riziká skôr, než sa stanú problémom.
                            </p>
                        </div>
                        <div className="w-full md:w-1/3 flex justify-center">
                            <div className="w-32 h-32 bg-blue-100 dark:bg-blue-900/30 rounded-full flex items-center justify-center text-blue-600 dark:text-blue-400">
                                <i className="fas fa-lightbulb text-5xl"></i>
                            </div>
                        </div>
                    </div>
                </div>

                {/* Technology Section */}
                <div className="app-card p-8 md:p-10">
                     <div className="flex flex-col md:flex-row-reverse gap-8 items-center">
                        <div className="flex-1">
                            <h2 className="text-2xl md:text-3xl font-bold text-gray-900 dark:text-white mb-4">Technológia</h2>
                            <p className="text-base text-gray-600 dark:text-gray-300 leading-relaxed mb-4">
                                Sme viac než len agregátor dát. Naše riešenie využíva najmodernejšie technológie:
                            </p>
                            <ul className="space-y-3">
                                <li className="flex items-start gap-3">
                                    <i className="fas fa-check-circle text-green-500 mt-1"></i>
                                    <span className="text-base text-gray-700 dark:text-gray-300"><strong>Google Gemini AI:</strong> Prekladá zložité finančné výkazy do zrozumiteľnej reči.</span>
                                </li>
                                <li className="flex items-start gap-3">
                                    <i className="fas fa-check-circle text-green-500 mt-1"></i>
                                    <span className="text-base text-gray-700 dark:text-gray-300"><strong>Real-time API:</strong> Napojenie na Finančnú správu, Sociálnu poisťovňu a obchodný register v reálnom čase.</span>
                                </li>
                                <li className="flex items-start gap-3">
                                    <i className="fas fa-check-circle text-green-500 mt-1"></i>
                                    <span className="text-base text-gray-700 dark:text-gray-300"><strong>Grafová databáza:</strong> Vizualizácia skrytých prepojení medzi osobami a firmami.</span>
                                </li>
                            </ul>
                        </div>
                         <div className="w-full md:w-1/3 flex justify-center">
                            <div className="w-32 h-32 bg-purple-100 dark:bg-purple-900/30 rounded-full flex items-center justify-center text-purple-600 dark:text-purple-400">
                                <i className="fas fa-microchip text-5xl"></i>
                            </div>
                        </div>
                    </div>
                </div>

                {/* Values Grid */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                    <div className="app-card p-6 text-center">
                        <i className="fas fa-shield-alt text-4xl text-blue-600 mb-4"></i>
                        <h3 className="text-lg font-bold text-gray-900 dark:text-white mb-2">Bezpečnosť</h3>
                        <p className="text-sm text-gray-500">Vaše dáta a vyhľadávania sú u nás v bezpečí, chránené šifrovaním.</p>
                    </div>
                    <div className="app-card p-6 text-center">
                        <i className="fas fa-search text-4xl text-blue-600 mb-4"></i>
                        <h3 className="text-lg font-bold text-gray-900 dark:text-white mb-2">Objektivita</h3>
                        <p className="text-sm text-gray-500">Poskytujeme len overené fakty z oficiálnych štátnych registrov.</p>
                    </div>
                    <div className="app-card p-6 text-center">
                        <i className="fas fa-users text-4xl text-blue-600 mb-4"></i>
                        <h3 className="text-lg font-bold text-gray-900 dark:text-white mb-2">Komunita</h3>
                        <p className="text-sm text-gray-500">Budujeme komunitu zodpovedných podnikateľov na Slovensku.</p>
                    </div>
                </div>
            </div>
        </div>
    );
};
