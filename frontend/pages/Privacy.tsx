
import React from 'react';

export const Privacy: React.FC = () => {
    return (
        <div className="max-w-4xl mx-auto w-full animate-fade-in py-10">
            <h1 className="text-3xl md:text-4xl font-bold text-gray-900 dark:text-white mb-8 text-center">
                Ochrana súkromia
            </h1>
            
            <div className="app-card p-8 md:p-12 prose dark:prose-invert max-w-none">
                <p className="text-lg text-gray-600 dark:text-gray-300 mb-6">
                    Vaše súkromie je pre nás prioritou. Tento dokument vysvetľuje, ako <strong>cistafirma.sk</strong> spracúva, ukladá a chráni vaše osobné údaje v súlade s nariadením GDPR a platnou legislatívou Slovenskej republiky.
                </p>

                <h3 className="text-xl font-bold text-gray-900 dark:text-white mt-8 mb-4">1. Prevádzkovateľ údajov</h3>
                <p className="text-base text-gray-600 dark:text-gray-400 mb-4">
                    Prevádzkovateľom portálu je spoločnosť DataTech s.r.o. (fiktívna spoločnosť pre účely dema), so sídlom Digitálna 1, 811 01 Bratislava. V prípade otázok nás kontaktujte na <a href="mailto:privacy@cistafirma.sk" className="text-blue-600 hover:underline">privacy@cistafirma.sk</a>.
                </p>

                <h3 className="text-xl font-bold text-gray-900 dark:text-white mt-8 mb-4">2. Aké údaje zbierame?</h3>
                <ul className="list-disc pl-5 space-y-2 text-base text-gray-600 dark:text-gray-400 mb-4">
                    <li><strong>Identifikačné údaje:</strong> Meno, priezvisko, používateľské meno (pre registrovaných používateľov).</li>
                    <li><strong>Kontaktné údaje:</strong> E-mailová adresa.</li>
                    <li><strong>Technické údaje:</strong> IP adresa, typ prehliadača, logy o prístupe (pre bezpečnostné účely).</li>
                    <li><strong>História vyhľadávania:</strong> Pre účely funkcie "História" vo vašom profile (tieto údaje sú súkromné a viditeľné len pre vás).</li>
                </ul>

                <h3 className="text-xl font-bold text-gray-900 dark:text-white mt-8 mb-4">3. Účel spracovania</h3>
                <p className="text-base text-gray-600 dark:text-gray-400 mb-4">
                    Údaje spracúvame za účelom poskytovania služby monitoringu firiem, správy používateľského účtu, fakturácie (pri platených plánoch) a zlepšovania našich služieb.
                </p>

                <h3 className="text-xl font-bold text-gray-900 dark:text-white mt-8 mb-4">4. Vaše práva</h3>
                <p className="text-base text-gray-600 dark:text-gray-400 mb-4">
                    Máte právo kedykoľvek požiadať o prístup k vašim údajom, ich opravu, vymazanie ("právo na zabudnutie") alebo obmedzenie spracovania. Svoje práva môžete uplatniť prostredníctvom nastavení v profile alebo emailom.
                </p>

                <div className="mt-8 p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg border border-blue-100 dark:border-blue-800">
                    <p className="text-sm text-blue-800 dark:text-blue-300">
                        <strong>Poznámka:</strong> Údaje o firmách (IČO, dlhy, atď.), ktoré zobrazujeme, sú verejne dostupné údaje zo štátnych registrov a nevzťahuje sa na ne ochrana osobných údajov fyzických osôb v rovnakom rozsahu, pokiaľ nejde o údaje dotýkajúce sa konkrétnych fyzických osôb (napr. rodné čísla, ktoré nezobrazujeme).
                    </p>
                </div>
            </div>
        </div>
    );
};
