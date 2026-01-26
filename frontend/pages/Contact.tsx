
import React, { useState } from 'react';

export const Contact: React.FC = () => {
    const [formState, setFormState] = useState({ name: '', email: '', message: '' });
    const [isSent, setIsSent] = useState(false);

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        // Mock send
        setTimeout(() => {
            setIsSent(true);
            setFormState({ name: '', email: '', message: '' });
        }, 1000);
    };

    return (
        <div className="max-w-5xl mx-auto w-full animate-fade-in py-10">
            <div className="text-center mb-12">
                <h1 className="text-3xl md:text-4xl font-bold text-gray-900 dark:text-white mb-4">
                    Kontaktujte nás
                </h1>
                <p className="text-lg text-gray-600 dark:text-gray-400">
                    Máte otázky alebo pripomienky? Sme tu pre vás.
                </p>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-12">
                {/* Contact Info */}
                <div className="space-y-6">
                    <div className="app-card p-6 flex items-start gap-4">
                        <div className="w-12 h-12 bg-blue-100 dark:bg-blue-900/30 rounded-lg flex items-center justify-center text-blue-600 dark:text-blue-400 flex-shrink-0">
                            <i className="fas fa-envelope text-xl"></i>
                        </div>
                        <div>
                            <h3 className="text-lg font-bold text-gray-900 dark:text-white mb-1">Email</h3>
                            <p className="text-gray-600 dark:text-gray-400 text-sm mb-2">Pre všeobecné otázky a podporu:</p>
                            <a href="mailto:info@cistafirma.sk" className="text-blue-600 hover:underline font-medium">info@cistafirma.sk</a>
                        </div>
                    </div>

                    <div className="app-card p-6 flex items-start gap-4">
                        <div className="w-12 h-12 bg-blue-100 dark:bg-blue-900/30 rounded-lg flex items-center justify-center text-blue-600 dark:text-blue-400 flex-shrink-0">
                            <i className="fas fa-briefcase text-xl"></i>
                        </div>
                        <div>
                            <h3 className="text-lg font-bold text-gray-900 dark:text-white mb-1">Obchodné oddelenie</h3>
                            <p className="text-gray-600 dark:text-gray-400 text-sm mb-2">Pre B2B spoluprácu a API integrácie:</p>
                            <a href="mailto:sales@cistafirma.sk" className="text-blue-600 hover:underline font-medium">sales@cistafirma.sk</a>
                        </div>
                    </div>

                    <div className="app-card p-6 flex items-start gap-4">
                         <div className="w-12 h-12 bg-blue-100 dark:bg-blue-900/30 rounded-lg flex items-center justify-center text-blue-600 dark:text-blue-400 flex-shrink-0">
                            <i className="fas fa-map-marker-alt text-xl"></i>
                        </div>
                        <div>
                            <h3 className="text-lg font-bold text-gray-900 dark:text-white mb-1">Korešpondenčná adresa</h3>
                            <p className="text-gray-600 dark:text-gray-400 text-sm">
                                DataTech Solutions s.r.o.<br/>
                                Digitálny Park II<br/>
                                Einsteinova 25<br/>
                                851 01 Bratislava
                            </p>
                        </div>
                    </div>
                </div>

                {/* Contact Form */}
                <div className="app-card p-8">
                    <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-6">Napíšte nám</h2>
                    
                    {isSent ? (
                        <div className="text-center py-12">
                            <div className="w-16 h-16 bg-green-100 dark:bg-green-900/30 rounded-full flex items-center justify-center text-green-600 dark:text-green-400 mx-auto mb-4">
                                <i className="fas fa-check text-2xl"></i>
                            </div>
                            <h3 className="text-xl font-bold text-gray-900 dark:text-white mb-2">Správa odoslaná!</h3>
                            <p className="text-base text-gray-600 dark:text-gray-400 mb-6">Ďakujeme za vašu správu. Ozveme sa vám čo najskôr.</p>
                            <button onClick={() => setIsSent(false)} className="btn btn-outline">Poslať ďalšiu správu</button>
                        </div>
                    ) : (
                        <form onSubmit={handleSubmit} className="space-y-4">
                            <div className="form-group">
                                <label className="form-label">Meno a Priezvisko</label>
                                <input 
                                    type="text" 
                                    required
                                    className="app-input"
                                    placeholder="Jozef Mrkvička"
                                    value={formState.name}
                                    onChange={e => setFormState({...formState, name: e.target.value})}
                                />
                            </div>
                            <div className="form-group">
                                <label className="form-label">Email</label>
                                <input 
                                    type="email" 
                                    required
                                    className="app-input"
                                    placeholder="jozef@firma.sk"
                                    value={formState.email}
                                    onChange={e => setFormState({...formState, email: e.target.value})}
                                />
                            </div>
                            <div className="form-group">
                                <label className="form-label">Správa</label>
                                <textarea 
                                    required
                                    rows={5}
                                    className="app-input resize-none"
                                    placeholder="Ako vám môžeme pomôcť?"
                                    value={formState.message}
                                    onChange={e => setFormState({...formState, message: e.target.value})}
                                ></textarea>
                            </div>
                            <button type="submit" className="btn btn-primary w-full py-3">
                                Odoslať správu <i className="fas fa-paper-plane ml-2"></i>
                            </button>
                        </form>
                    )}
                </div>
            </div>
        </div>
    );
};
