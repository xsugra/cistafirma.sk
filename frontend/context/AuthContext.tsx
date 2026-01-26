
import React, { createContext, useContext, useState, useEffect } from 'react';
import { api } from '../api';
import type { User } from '../types';

interface AuthContextType {
    user: User | null;
    isAuthenticated: boolean;
    login: (user: User, token: string) => void;
    logout: () => void;
    isLoading: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const [user, setUser] = useState<User | null>(null);
    const [isLoading, setIsLoading] = useState(true);

    const logout = () => {
        localStorage.removeItem('token');
        setUser(null);
    };

    const login = (userData: User, token: string) => {
        localStorage.setItem('token', token);
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
            const token = localStorage.getItem('token');
            if (token) {
                try {
                    // This will now use the centralized 'request' in api.js.
                    // If it fails with 401, the event listener above will handle it.
                    const userData = await api.getProfile();
                    // @ts-ignore
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
