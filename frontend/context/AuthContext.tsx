
import React, { createContext, useContext, useState, useEffect } from 'react';
import { api } from '../api';
import {
    clearSession,
    getAccessToken,
    getRefreshToken,
    saveSession,
} from '../lib/tokenStore';
import type { TokenBundle } from '../lib/tokenStore';
import type { User } from '../types';

interface AuthContextType {
    user: User | null;
    isAuthenticated: boolean;
    /**
     * `remember` is the "Zapamätať prihlásenie" box: it decides whether the
     * session goes to `localStorage` (survives closing the browser) or to
     * `sessionStorage` (ends with the tab). The box had no state at all before
     * this, so it promised something it never did.
     */
    login: (user: User, tokens: TokenBundle, remember: boolean) => void;
    logout: () => void;
    isLoading: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const [user, setUser] = useState<User | null>(null);
    const [isLoading, setIsLoading] = useState(true);

    const logout = () => {
        clearSession();
        setUser(null);
    };

    const login = (userData: User, tokens: TokenBundle, remember: boolean) => {
        saveSession(tokens, remember);
        setUser(userData);
    };

    // Listen for global 401 Unauthorized events from api.js
    useEffect(() => {
        const handleUnauthorized = () => {
            console.warn("Session expired. Logging out.");
            logout();
        };

        window.addEventListener('auth:unauthorized', handleUnauthorized);
        return () => {
            window.removeEventListener('auth:unauthorized', handleUnauthorized);
        };
    }, []);

    useEffect(() => {
        const initAuth = async () => {
            // Either token is enough to try. With a refresh token and no access
            // token the request goes out unauthenticated, is refused, and comes
            // back on the refresh -- which is the same path an expired access
            // token takes, so there is no second one to write here.
            if (getAccessToken() || getRefreshToken()) {
                try {
                    // This will now use the centralized 'request' in api.js.
                    // If it fails with 401, the event listener above will handle it.
                    const userData = await api.getProfile();
                    setUser(userData);
                } catch (error) {
                    console.error("Auth initialization failed", error);
                    // If fetching profile fails (e.g. server down or 401), clear local token
                    logout();
                }
            }
            setIsLoading(false);
        };
        initAuth();
    }, []);

    return (
        <AuthContext.Provider value={{ 
            user, 
            isAuthenticated: !!user, 
            login, 
            logout,
            isLoading 
        }}>
            {children}
        </AuthContext.Provider>
    );
};

export const useAuth = () => {
    const context = useContext(AuthContext);
    if (!context) {
        throw new Error('useAuth must be used within an AuthProvider');
    }
    return context;
};
