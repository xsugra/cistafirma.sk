
import React from 'react';
import { ROUTES } from '../constants';

interface FooterProps {
    onNavigate?: (route: string) => void;
}

export const Footer: React.FC<FooterProps> = ({ onNavigate }) => {
  // Helper to handle navigation if available, otherwise fallback (though in this app it should always be available)
  const handleNav = (route: string, e: React.MouseEvent) => {
      e.preventDefault();
      if (onNavigate) {
          onNavigate(route);
          window.scrollTo(0, 0);
      }
  };

  return (
    <footer className="mt-auto py-8 bg-white dark:bg-slate-950 border-t border-gray-200 dark:border-slate-900 transition-colors duration-300 relative z-20">
        <div className="container mx-auto px-4">
            <div className="flex flex-col md:flex-row justify-between items-center gap-4">
                <div className="text-gray-500 text-sm text-center md:text-left">
                    &copy; {new Date().getFullYear()} cistafirma.sk. <br className="md:hidden"/>Všetky práva vyhradené.
                </div>
                <div className="flex flex-wrap justify-center gap-6 text-sm text-gray-500 dark:text-gray-400">
                    <a href="#" onClick={(e) => handleNav(ROUTES.ABOUT, e)} className="hover:text-blue-600 dark:hover:text-blue-400 transition-colors">O Nás</a>
                    <a href="#" onClick={(e) => handleNav(ROUTES.PRIVACY, e)} className="hover:text-blue-600 dark:hover:text-blue-400 transition-colors">Ochrana súkromia</a>
                    <a href="#" onClick={(e) => handleNav(ROUTES.TERMS, e)} className="hover:text-blue-600 dark:hover:text-blue-400 transition-colors">Podmienky používania</a>
                    <a href="#" onClick={(e) => handleNav(ROUTES.CONTACT, e)} className="hover:text-blue-600 dark:hover:text-blue-400 transition-colors">Kontakt</a>
                </div>
            </div>
        </div>
    </footer>
  );
};
