import React, {useState, useEffect, useCallback} from 'react';
import {ThemeProvider} from './context/ThemeContext';
import {AuthProvider, useAuth} from './context/AuthContext';
import {Header} from './components/Header';
import {Footer} from './components/Footer';
import {VantaBackground} from './components/VantaBackground';
import {Home} from './pages/Home';
import {Monitoring} from './pages/Monitoring';
import {Blog} from './pages/Blog';
import {Pricing} from './pages/Pricing';
import {Login} from './pages/Login';
import {Register} from './pages/Register';
import {Profile} from './pages/Profile';
import {About} from './pages/About';
import {Privacy} from './pages/Privacy';
import {Terms} from './pages/Terms';
import {Contact} from './pages/Contact';
import {NotFound} from './pages/NotFound';
import {AdminApp} from './admin/AdminApp';
import {ROUTES} from './constants';
import './styles/animations.css';

// --- ERROR BOUNDARY ---
// Prevents the "White Screen of Death" by catching render errors
class ErrorBoundary extends React.Component<{ children: React.ReactNode }, { hasError: boolean, error: Error | null }> {
    constructor(props: any) {
        super(props);
        this.state = {hasError: false, error: null};
    }

    static getDerivedStateFromError(error: Error) {
        return {hasError: true, error};
    }

    componentDidCatch(error: Error, errorInfo: any) {
        console.error("Uncaught error:", error, errorInfo);
    }

    render() {
        if (this.state.hasError) {
            return (
                <div
                    className="flex flex-col items-center justify-center min-h-screen text-center p-4 bg-white dark:bg-slate-950 text-gray-900 dark:text-white">
                    <div
                        className="bg-red-50 dark:bg-red-900/20 p-6 rounded-xl border border-red-200 dark:border-red-800 max-w-lg">
                        <i className="fas fa-bug text-4xl text-red-500 mb-4"></i>
                        <h2 className="text-2xl font-bold mb-2">Nastala neočakávaná chyba</h2>
                        <p className="mb-4 text-gray-600 dark:text-gray-300">Aplikácia narazila na problém a nemôže
                            pokračovať.</p>
                        <pre
                            className="text-left bg-gray-100 dark:bg-black p-3 rounded text-xs font-mono overflow-auto max-h-40 mb-4 border border-gray-200 dark:border-slate-800">
                            {this.state.error?.toString()}
                        </pre>
                        <button onClick={() => window.location.reload()} className="btn btn-primary">
                            <i className="fas fa-sync-alt mr-2"></i> Obnoviť stránku
                        </button>
                    </div>
                </div>
            );
        }
        return this.props.children;
    }
}

// --- ROUTER LOGIC ---

// Detect if we are serving from a subpath (like /static/ in Django/Vite dev)
const getBasePath = () => {
    const path = window.location.pathname;
    return path.startsWith('/static') ? '/static' : '';
};

const normalizePath = (path: string) => {
    let cleanPath = path;
    // Remove base path prefix if present
    if (cleanPath.startsWith('/static')) {
        cleanPath = cleanPath.replace('/static', '');
    }
    // Remove trailing slash for consistency (except for root '/')
    if (cleanPath.length > 1 && cleanPath.endsWith('/')) {
        cleanPath = cleanPath.slice(0, -1);
    }
    // Default to root
    if (!cleanPath) cleanPath = '/';
    return cleanPath;
};

const getRouteFromPath = (path: string): { id: string, params?: any } => {
    const url = new URL(window.location.origin + path);
    const normalized = normalizePath(url.pathname);
    const params: any = {};
    
    // Parse query params (specifically for ico)
    if (url.searchParams.has('ico')) {
        params.ico = url.searchParams.get('ico');
    }

    switch (normalized) {
        case '/':
            return {id: ROUTES.HOME};
        case '/monitoring':
            return {id: ROUTES.MONITORING, params};
        case '/blog':
            return {id: ROUTES.BLOG};
        case '/pricing':
            return {id: ROUTES.PRICING};
        case '/about':
            return {id: ROUTES.ABOUT};
        case '/contact':
            return {id: ROUTES.CONTACT};
        case '/login':
            return {id: ROUTES.LOGIN};
        case '/register':
            return {id: ROUTES.REGISTER};
        case '/profile':
            return {id: ROUTES.PROFILE};
        case '/terms':
            return {id: ROUTES.TERMS};
        case '/privacy':
            return {id: ROUTES.PRIVACY};
        case '/admin':
            return {id: ROUTES.ADMIN};
        default:
            return {id: ROUTES.NOT_FOUND};
    }
};

const getPathFromRoute = (routeId: string, params?: any): string => {
    let path = '/';
    switch (routeId) {
        case ROUTES.HOME:
            path = '/';
            break;
        case ROUTES.MONITORING:
            path = '/monitoring';
            break;
        case ROUTES.BLOG:
            path = '/blog';
            break;
        case ROUTES.PRICING:
            path = '/pricing';
            break;
        case ROUTES.LOGIN:
            path = '/login';
            break;
        case ROUTES.REGISTER:
            path = '/register';
            break;
        case ROUTES.PROFILE:
            path = '/profile';
            break;
        case ROUTES.ABOUT:
            path = '/about';
            break;
        case ROUTES.CONTACT:
            path = '/contact';
            break;
        case ROUTES.TERMS:
            path = '/terms';
            break;
        case ROUTES.PRIVACY:
            path = '/privacy';
            break;
        case ROUTES.ADMIN:
            path = '/admin';
            break;
        default:
            path = '/';
    }

    if (params && params.ico) {
        const query = new URLSearchParams();
        query.set('ico', params.ico);
        path += '?' + query.toString();
    }
    
    return path;
};

// Main App Content
const AppContent: React.FC = () => {
    const [view, setView] = useState<{ id: string, params?: any }>({id: ROUTES.HOME});
    const {user, isAuthenticated, isLoading} = useAuth();

    // 1. Initial Load & Popstate Listener (Back/Forward buttons)
    useEffect(() => {
        const handleLocationChange = () => {
            const currentPath = window.location.pathname + window.location.search;
            const newView = getRouteFromPath(currentPath);
            setView(newView);
        };

        // Handle initial load
        handleLocationChange();

        // Listen for back/forward navigation
        window.addEventListener('popstate', handleLocationChange);
        return () => window.removeEventListener('popstate', handleLocationChange);
    }, []);

    // 2. Navigation Function (Updates State + Pushes to History)
    const handleNavigate = useCallback((route: string, params?: any) => {
        setView({id: route, params});

        const basePath = getBasePath();
        const routePath = getPathFromRoute(route, params);

        // Construct full URL
        const fullPath = basePath + (routePath === '/' ? '' : routePath);
        const finalUrl = fullPath === '' ? '/' : fullPath;

        window.history.pushState({}, '', finalUrl);
        window.scrollTo(0, 0);
    }, []);

    // 3. Protected Route Guard
    useEffect(() => {
        if (!isLoading && !isAuthenticated && view.id === ROUTES.PROFILE) {
            handleNavigate(ROUTES.LOGIN);
        }
    }, [view.id, isAuthenticated, isLoading, handleNavigate]);

    const renderPage = () => {
        if (isLoading) {
            return <div className="flex h-[50vh] items-center justify-center">
                <div className="w-10 h-10 border-4 border-brand border-t-transparent rounded-full animate-spin"></div>
            </div>;
        }

        switch (view.id) {
            case ROUTES.HOME:
                return <Home onNavigate={handleNavigate}/>;
            case ROUTES.MONITORING:
                return <Monitoring initialSearch={view.params?.ico}/>;
            case ROUTES.BLOG:
                return <Blog/>;
            case ROUTES.PRICING:
                return <Pricing/>;
            case ROUTES.ABOUT:
                return <About/>;
            case ROUTES.PRIVACY:
                return <Privacy/>;
            case ROUTES.TERMS:
                return <Terms/>;
            case ROUTES.CONTACT:
                return <Contact/>;
            case ROUTES.LOGIN:
                return <Login
                    onSuccess={() => handleNavigate(ROUTES.HOME)}
                    onRegisterClick={() => handleNavigate(ROUTES.REGISTER)}
                />;
            case ROUTES.REGISTER:
                return <Register
                    onSuccess={() => handleNavigate(ROUTES.HOME)}
                    onLoginClick={() => handleNavigate(ROUTES.LOGIN)}
                />;
            case ROUTES.PROFILE:
                return isAuthenticated ? <Profile onNavigate={handleNavigate}/> : <div/>;
            case ROUTES.NOT_FOUND:
                return <NotFound onNavigate={handleNavigate}/>;
            default:
                return <NotFound onNavigate={handleNavigate}/>;
        }
    };

    // Admin panel — takes over the full viewport, no Header/Footer
    if (view.id === ROUTES.ADMIN) {
        if (!isAuthenticated) {
            handleNavigate(ROUTES.LOGIN);
            return null;
        }
        return (
            <ErrorBoundary>
                <AdminApp
                    onExit={() => handleNavigate(ROUTES.HOME)}
                    userName={user?.email || user?.username}
                />
            </ErrorBoundary>
        );
    }

    return (
        <div
            className="relative z-10 flex flex-col min-h-screen text-light-text dark:text-dark-text transition-colors duration-300">
            <Header activeRoute={view.id} onNavigate={handleNavigate}/>

            <main className="flex-grow container mx-auto px-4 py-8 relative z-10">
                <ErrorBoundary>
                    {renderPage()}
                </ErrorBoundary>
            </main>

            <Footer onNavigate={handleNavigate}/>
        </div>
    );
}

const App: React.FC = () => {
    return (
        <ErrorBoundary>
            <ThemeProvider>
                <AuthProvider>
                    <VantaBackground/>
                    <AppContent/>
                </AuthProvider>
            </ThemeProvider>
        </ErrorBoundary>
    );
};

export default App;
