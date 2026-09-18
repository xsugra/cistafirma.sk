import React, {useState, useEffect} from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import {BrandLogo} from './BrandLogo';
import {ROUTES} from '../constants';
import {ThemeToggle} from './ThemeToggle';
import {useAuth} from '../context/AuthContext';

export const Header: React.FC = () => {
    const navigate = useNavigate();
    const location = useLocation();
    const {isAuthenticated, user, logout} = useAuth();
    const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
    const [scrolled, setScrolled] = useState(false);

    useEffect(() => {
        const handleScroll = () => {
            setScrolled(window.scrollY > 20);
        };
        window.addEventListener('scroll', handleScroll);
        return () => window.removeEventListener('scroll', handleScroll);
    }, []);

    const handleNav = (route: string) => {
        setIsMobileMenuOpen(false);
        navigate(route);
    };

    const handleLogout = () => {
        setIsMobileMenuOpen(false);
        logout();
        navigate(ROUTES.HOME);
    };

    const activeRoute = location.pathname;
    const displayName = user?.firstName || user?.username || user?.email?.split('@')[0] || 'User';

    return (
        <>
            <header className={`header-wrapper ${scrolled ? 'shadow-md' : ''}`}>
                <div className="container mx-auto px-4">
                    <div className="flex justify-between items-center h-16 md:h-20 transition-all duration-300">

                        <div className="flex-shrink-0 z-50">
                            <BrandLogo onClick={() => handleNav(ROUTES.HOME)}/>
                        </div>

                        <nav className="hidden lg:flex items-center space-x-6 xl:space-x-8">
                            <button onClick={() => handleNav(ROUTES.HOME)}
                                    className={`nav-link bg-transparent border-0 ${activeRoute === ROUTES.HOME ? 'active' : ''}`}>DOMOV
                            </button>
                            <button onClick={() => handleNav(ROUTES.MONITORING)}
                                    className={`nav-link bg-transparent border-0 ${activeRoute === ROUTES.MONITORING ? 'active' : ''}`}>MONITORING
                            </button>
                            <button onClick={() => handleNav(ROUTES.BLOG)}
                                    className={`nav-link bg-transparent border-0 ${activeRoute === ROUTES.BLOG ? 'active' : ''}`}>BLOG
                            </button>
                            <button onClick={() => handleNav(ROUTES.API_DOCS)}
                                    className={`nav-link bg-transparent border-0 ${activeRoute === ROUTES.API_DOCS ? 'active' : ''}`}>API
                            </button>
                        </nav>

                        <div className="flex items-center gap-2 md:gap-4 z-50">
                            <ThemeToggle/>

                            <div className="hidden lg:flex items-center gap-4">
                                {!isAuthenticated ? (
                                    <>
                                        <button
                                            onClick={() => handleNav(ROUTES.LOGIN)}
                                            className={`nav-link bg-transparent border-0 ${activeRoute === ROUTES.LOGIN ? 'active' : ''}`}
                                        >
                                            Prihlásiť sa
                                        </button>
                                        <button
                                            onClick={() => handleNav(ROUTES.REGISTER)}
                                            className="btn btn-primary rounded-full px-5 shadow-lg shadow-blue-500/30 hover:scale-105"
                                        >
                                            Registrácia
                                        </button>
                                    </>
                                ) : (
                                    <div className="flex items-center gap-3">
                                        {user?.isStaff && (
                                            <button
                                                onClick={() => handleNav(ROUTES.ADMIN)}
                                                className="flex items-center gap-1.5 px-3 py-1.5 rounded-full transition-colors border bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800 text-blue-600 dark:text-blue-400 hover:bg-blue-100 dark:hover:bg-blue-900/40 text-sm font-medium"
                                                title="Admin panel"
                                            >
                                                <i className="fas fa-shield-alt text-xs"></i>
                                                Admin
                                            </button>
                                        )}
                                        <button
                                            onClick={() => handleNav(ROUTES.PROFILE)}
                                            className={`flex items-center gap-2 px-3 py-1.5 rounded-full transition-colors border ${activeRoute === ROUTES.PROFILE ? 'bg-blue-100 dark:bg-blue-900 border-blue-500 text-blue-600 dark:text-blue-300' : 'bg-gray-100 dark:bg-slate-800 border-gray-200 dark:border-slate-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-slate-700'}`}
                                            title="Môj profil"
                                        >
                                            <i className="fas fa-user-circle text-lg"></i>
                                            <span className="text-sm font-medium">{displayName}</span>
                                        </button>

                                        <button
                                            onClick={handleLogout}
                                            className="btn btn-ghost btn-icon hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20"
                                            title="Odhlásiť sa"
                                        >
                                            <i className="fas fa-sign-out-alt"></i>
                                        </button>
                                    </div>
                                )}
                            </div>

                            <button
                                className="lg:hidden p-2 text-gray-600 dark:text-gray-300 hover:text-blue-600 dark:hover:text-blue-400 focus:outline-none transition-colors"
                                onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
                                aria-label="Menu"
                            >
                                <div className="w-6 h-6 flex flex-col justify-center gap-1.5">
                                    <span
                                        className={`block h-0.5 w-full bg-current transform transition-all duration-300 ${isMobileMenuOpen ? 'rotate-45 translate-y-2' : ''}`}></span>
                                    <span
                                        className={`block h-0.5 w-full bg-current transition-all duration-300 ${isMobileMenuOpen ? 'opacity-0' : ''}`}></span>
                                    <span
                                        className={`block h-0.5 w-full bg-current transform transition-all duration-300 ${isMobileMenuOpen ? '-rotate-45 -translate-y-2' : ''}`}></span>
                                </div>
                            </button>
                        </div>
                    </div>
                </div>
            </header>

            <div
                // `pt-24` (6rem) is what clears the header, and the header is
                // now taller by the top inset -- so the sum, written out, rather
                // than `pt-24` beside a `.safe-*` class that would *replace* it
                // instead of adding to it. The overlay's own background still
                // reaches the glass; only the content is inset, and the bottom
                // keeps the last item off the home indicator. Underscores are
                // Tailwind's spaces in an arbitrary value -- `calc(6rem+env(…))`
                // with no spaces is not valid CSS.
                className={`fixed inset-0 z-40 bg-white/95 dark:bg-slate-950/95 backdrop-blur-xl transition-all duration-300 lg:hidden flex flex-col pt-[calc(6rem_+_env(safe-area-inset-top))] pb-[env(safe-area-inset-bottom)] px-6
            ${isMobileMenuOpen ? 'opacity-100 pointer-events-auto translate-x-0' : 'opacity-0 pointer-events-none translate-x-full'}`}
            >
                <nav className="flex flex-col space-y-6 text-center text-lg">
                    <button onClick={() => handleNav(ROUTES.HOME)}
                            className={`py-2 border-b border-gray-100 dark:border-slate-800 w-full ${activeRoute === ROUTES.HOME ? 'text-blue-600 font-bold' : 'text-gray-800 dark:text-gray-200'}`}>DOMOV
                    </button>
                    <button onClick={() => handleNav(ROUTES.MONITORING)}
                            className={`py-2 border-b border-gray-100 dark:border-slate-800 w-full ${activeRoute === ROUTES.MONITORING ? 'text-blue-600 font-bold' : 'text-gray-800 dark:text-gray-200'}`}>MONITORING
                    </button>
                    <button onClick={() => handleNav(ROUTES.BLOG)}
                            className={`py-2 border-b border-gray-100 dark:border-slate-800 w-full ${activeRoute === ROUTES.BLOG ? 'text-blue-600 font-bold' : 'text-gray-800 dark:text-gray-200'}`}>BLOG
                    </button>
                    <button onClick={() => handleNav(ROUTES.API_DOCS)}
                            className={`py-2 border-b border-gray-100 dark:border-slate-800 w-full ${activeRoute === ROUTES.API_DOCS ? 'text-blue-600 font-bold' : 'text-gray-800 dark:text-gray-200'}`}>API
                    </button>

                    {!isAuthenticated ? (
                        <div className="flex flex-col gap-4 mt-8">
                            <button
                                onClick={() => handleNav(ROUTES.LOGIN)}
                                className="btn btn-outline w-full py-3 rounded-xl"
                            >
                                Prihlásiť sa
                            </button>
                            <button
                                onClick={() => handleNav(ROUTES.REGISTER)}
                                className="btn btn-primary w-full py-3 rounded-xl shadow-lg"
                            >
                                Registrácia
                            </button>
                        </div>
                    ) : (
                        <div
                            className="flex flex-col gap-4 mt-4 bg-gray-50 dark:bg-slate-900 p-6 rounded-2xl border border-gray-100 dark:border-slate-800">
                            <div className="flex items-center gap-4 justify-center mb-2">
                                <div
                                    className="w-12 h-12 rounded-full bg-blue-100 dark:bg-blue-900 text-blue-600 dark:text-blue-300 flex items-center justify-center text-xl font-bold">
                                    {displayName.charAt(0).toUpperCase()}
                                </div>
                                <div className="text-left">
                                    <p className="font-bold text-gray-900 dark:text-white">{displayName}</p>
                                    <p className="text-xs text-gray-500">{user?.email}</p>
                                </div>
                            </div>
                            {user?.isStaff && (
                                <button
                                    onClick={() => handleNav(ROUTES.ADMIN)}
                                    className="btn w-full bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400 border border-blue-200 dark:border-blue-800"
                                >
                                    <i className="fas fa-shield-alt mr-2"></i>Admin Panel
                                </button>
                            )}
                            <button
                                onClick={() => handleNav(ROUTES.PROFILE)}
                                className="btn btn-primary w-full"
                            >
                                Môj Profil
                            </button>
                            <button
                                onClick={handleLogout}
                                className="btn btn-ghost w-full text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20"
                            >
                                Odhlásiť sa
                            </button>
                        </div>
                    )}
                </nav>
            </div>
        </>
    );
};
