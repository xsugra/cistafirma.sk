import React from 'react';
import { BrowserRouter, Routes, Route, Navigate, useNavigate } from 'react-router-dom';
import { ThemeProvider } from './context/ThemeContext';
import { AuthProvider, useAuth } from './context/AuthContext';
import { Header } from './components/Header';
import { Footer } from './components/Footer';
import { VantaBackground } from './components/VantaBackground';
import { Home } from './pages/Home';
import { Monitoring } from './pages/Monitoring';
import { Blog } from './pages/Blog';
import { Login } from './pages/Login';
import { Register } from './pages/Register';
import { Profile } from './pages/Profile';
import { About } from './pages/About';
import { Privacy } from './pages/Privacy';
import { Terms } from './pages/Terms';
import { Contact } from './pages/Contact';
import { NotFound } from './pages/NotFound';
import { ApiDocs } from './pages/ApiDocs';
import { AdminApp } from './admin/AdminApp';
import { ROUTES } from './constants';
import './styles/animations.css';

class ErrorBoundary extends React.Component<{ children: React.ReactNode }, { hasError: boolean; error: Error | null }> {
  constructor(props: any) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: any) {
    console.error('Uncaught error:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex flex-col items-center justify-center min-h-screen text-center p-4 bg-white dark:bg-slate-950 text-gray-900 dark:text-white">
          <div className="bg-red-50 dark:bg-red-900/20 p-6 rounded-xl border border-red-200 dark:border-red-800 max-w-lg">
            <i className="fas fa-bug text-4xl text-red-500 mb-4"></i>
            <h2 className="text-2xl font-bold mb-2">Nastala neočakávaná chyba</h2>
            <p className="mb-4 text-gray-600 dark:text-gray-300">
              Aplikácia narazila na problém a nemôže pokračovať.
            </p>
            <pre className="text-left bg-gray-100 dark:bg-black p-3 rounded text-xs font-mono overflow-auto max-h-40 mb-4 border border-gray-200 dark:border-slate-800">
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

const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="flex h-[50vh] items-center justify-center">
        <div className="w-10 h-10 border-4 border-brand border-t-transparent rounded-full animate-spin"></div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to={ROUTES.LOGIN} replace />;
  }

  return <>{children}</>;
};

const AdminRoute: React.FC = () => {
  const { isAuthenticated, isLoading, user } = useAuth();
  const navigate = useNavigate();

  if (isLoading) {
    return (
      <div className="flex h-[50vh] items-center justify-center">
        <div className="w-10 h-10 border-4 border-brand border-t-transparent rounded-full animate-spin"></div>
      </div>
    );
  }

  if (!isAuthenticated || !user?.isStaff) {
    return <Navigate to={ROUTES.HOME} replace />;
  }

  return (
    <ErrorBoundary>
      <AdminApp onExit={() => navigate(ROUTES.HOME)} userName={user?.email || user?.username} />
    </ErrorBoundary>
  );
};

const PublicLayout: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <div className="relative z-10 flex flex-col min-h-screen text-light-text dark:text-dark-text transition-colors duration-300">
    <Header />
    <main className="flex-grow container mx-auto px-4 py-8 relative z-10">
      <ErrorBoundary>{children}</ErrorBoundary>
    </main>
    <Footer />
  </div>
);

const AppContent: React.FC = () => {
  return (
    <Routes>
      <Route path={ROUTES.ADMIN} element={<AdminRoute />} />
      <Route
        path="*"
        element={
          <PublicLayout>
            <Routes>
              <Route path={ROUTES.HOME} element={<Home />} />
              <Route path={ROUTES.MONITORING} element={<Monitoring />} />
              <Route path={ROUTES.BLOG} element={<Blog />} />
              <Route path={ROUTES.ABOUT} element={<About />} />
              <Route path={ROUTES.PRIVACY} element={<Privacy />} />
              <Route path={ROUTES.TERMS} element={<Terms />} />
              <Route path={ROUTES.CONTACT} element={<Contact />} />
              <Route path={ROUTES.API_DOCS} element={<ApiDocs />} />
              <Route path={ROUTES.LOGIN} element={<Login />} />
              <Route path={ROUTES.REGISTER} element={<Register />} />
              <Route
                path={ROUTES.PROFILE}
                element={
                  <ProtectedRoute>
                    <Profile />
                  </ProtectedRoute>
                }
              />
              <Route path="*" element={<NotFound />} />
            </Routes>
          </PublicLayout>
        }
      />
    </Routes>
  );
};

const App: React.FC = () => {
  return (
    <ErrorBoundary>
      <BrowserRouter>
        <ThemeProvider>
          <AuthProvider>
            <VantaBackground />
            <AppContent />
          </AuthProvider>
        </ThemeProvider>
      </BrowserRouter>
    </ErrorBoundary>
  );
};

export default App;
