import React from 'react';
import { Link } from 'react-router-dom';
import { ROUTES } from '../constants';

export const Footer: React.FC = () => {
    return (
        <footer
            className="mt-auto py-8 bg-white dark:bg-slate-950 border-t border-gray-200 dark:border-slate-900 transition-colors duration-300 relative z-20">
            <div className="container mx-auto px-4">
                <div className="flex flex-col md:flex-row justify-between items-center gap-4">
                    <div className="flex items-center gap-4">
                        <div className="text-gray-500 text-sm text-center md:text-center">
                            &copy; {new Date().getFullYear()} cistafirma.sk
                            <br className="md:hidden"/> | Všetky práva vyhradené.
                        </div>
                    </div>
                    <div className="flex flex-wrap justify-center gap-6 text-sm text-gray-500 dark:text-gray-400">
                        <Link to={ROUTES.ABOUT}
                           className="hover:text-blue-600 dark:hover:text-blue-400 transition-colors">O Nás</Link>
                        <Link to={ROUTES.PRIVACY}
                           className="hover:text-blue-600 dark:hover:text-blue-400 transition-colors">Ochrana
                            súkromia</Link>
                        <Link to={ROUTES.TERMS}
                           className="hover:text-blue-600 dark:hover:text-blue-400 transition-colors">Podmienky
                            používania</Link>
                        <Link to={ROUTES.CONTACT}
                           className="hover:text-blue-600 dark:hover:text-blue-400 transition-colors">Kontakt</Link>
                    </div>
                </div>
            </div>
        </footer>
    );
};
