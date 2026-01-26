
import React from 'react';

export const Terms: React.FC = () => {
    return (
        <div className="max-w-4xl mx-auto w-full animate-fade-in py-10">
            <h1 className="text-3xl md:text-4xl font-bold text-gray-900 dark:text-white mb-8 text-center">
                Podmienky používania
            </h1>
            
            <div className="app-card p-8 md:p-12 prose dark:prose-invert max-w-none">
                <p className="text-sm text-gray-500 mb-6 font-medium">Platné od: 1. Januára 2025</p>
                
                <h3 className="text-xl font-bold text-gray-900 dark:text-white mt-6 mb-3">1. Úvodné ustanovenia</h3>
                <p className="text-base text-gray-600 dark:text-gray-400 mb-4">
                    Tieto podmienky upravujú používanie portálu <strong>cistafirma.sk</strong>. Registráciou alebo používaním služby vyjadrujete súhlas s týmito podmienkami. Služba slúži na informačné účely a nenahrádza oficiálne výpisy z verejných registrov pre právne úkony.
                </p>

                <h3 className="text-xl font-bold text-gray-900 dark:text-white mt-6 mb-3">2. Zodpovednosť za dáta</h3>
                <p className="text-base text-gray-600 dark:text-gray-400 mb-4">
                    Prevádzkovateľ vyvíja maximálne úsilie na zabezpečenie aktuálnosti a presnosti dát. Údaje sú preberané z tretích strán (Finančná správa, Obchodný register, poisťovne). Prevádzkovateľ nenesie zodpovednosť za chyby v pôvodných zdrojoch dát ani za škody spôsobené rozhodnutiami vykonanými na základe informácií z portálu.
                </p>

                <h3 className="text-xl font-bold text-gray-900 dark:text-white mt-6 mb-3">3. Používateľské konto</h3>
                <ul className="list-disc pl-5 space-y-2 text-base text-gray-600 dark:text-gray-400 mb-4">
                    <li>Používateľ je povinný chrániť svoje prihlasovacie údaje.</li>
                    <li>Je zakázané používať automatizované nástroje (boty) na sťahovanie dát bez API licencie.</li>
                    <li>Prevádzkovateľ si vyhradzuje právo zrušiť účet pri porušení podmienok.</li>
                </ul>

                <h3 className="text-xl font-bold text-gray-900 dark:text-white mt-6 mb-3">4. Platené služby a API</h3>
                <p className="text-base text-gray-600 dark:text-gray-400 mb-4">
                    Niektoré funkcie (napr. neobmedzené vyhľadávanie, API prístup) sú spoplatnené podľa aktuálneho <a href="#" className="text-blue-600 hover:underline">Cenníka</a>. Predplatné sa obnovuje automaticky, pokiaľ nie je zrušené pred koncom fakturačného obdobia.
                </p>

                <h3 className="text-xl font-bold text-gray-900 dark:text-white mt-6 mb-3">5. Zmena podmienok</h3>
                <p className="text-base text-gray-600 dark:text-gray-400 mb-4">
                    Prevádzkovateľ si vyhradzuje právo meniť tieto podmienky. O významných zmenách budeme informovať používateľov emailom alebo oznámením na stránke.
                </p>
            </div>
        </div>
    );
};
