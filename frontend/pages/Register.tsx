import React, {useState} from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import {api} from '../api';
import {AuthLayout} from '../components/AuthLayout';
import {ROUTES} from '../constants';
import {postAuthDestination} from '../utils/postAuthDestination';

export const Register: React.FC = () => {
    const navigate = useNavigate();
    const location = useLocation();
    const [formData, setFormData] = useState({
        firstName: '',
        lastName: '',
        username: '',
        email: '',
        password: '',
        confirmPassword: ''
    });

    const [showPassword, setShowPassword] = useState(false);
    const [showConfirmPassword, setShowConfirmPassword] = useState(false);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');

    const passwordsMatch = formData.password && formData.confirmPassword && formData.password === formData.confirmPassword;
    const isTypingConfirm = formData.confirmPassword.length > 0;

    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        setFormData({...formData, [e.target.name]: e.target.value});
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (formData.password !== formData.confirmPassword) {
            setError('Zadané heslá sa nezhodujú.');
            return;
        }
        setLoading(true);
        setError('');
        try {
            await api.register(formData);
            navigate(postAuthDestination(location.state), {replace: true});
        } catch (error: any) {
            setError(error.message || 'Registrácia zlyhala. Skúste to prosím znova.');
        } finally {
            setLoading(false);
        }
    };

    return (
        <AuthLayout
            title="Vytvoriť nový účet"
            subtitle="Získajte prístup k prémiovým funkciám a monitoringu."
        >
            {error && (
                <div
                    className="mb-6 p-4 bg-red-50 dark:bg-red-900/20 border-l-4 border-red-500 text-red-700 dark:text-red-300 text-sm rounded-r-lg flex items-center gap-3">
                    <i className="fas fa-exclamation-circle flex-shrink-0"></i>
                    <span>{error}</span>
                </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                        <label className="form-label">Meno</label>
                        <input
                            name="firstName"
                            type="text"
                            required
                            value={formData.firstName}
                            onChange={handleChange}
                            className="app-input"
                            placeholder="Jozef"
                        />
                    </div>
                    <div>
                        <label className="form-label">Priezvisko</label>
                        <input
                            name="lastName"
                            type="text"
                            required
                            value={formData.lastName}
                            onChange={handleChange}
                            className="app-input"
                            placeholder="Mrkvička"
                        />
                    </div>
                </div>

                <div>
                    <label className="form-label">Používateľské meno</label>
                    <div className="input-wrapper">
                        <i className="fas fa-user input-icon"></i>
                        <input
                            name="username"
                            type="text"
                            required
                            value={formData.username}
                            onChange={handleChange}
                            className="app-input"
                            placeholder="jmrkvicka"
                        />
                    </div>
                </div>

                <div>
                    <label className="form-label">Email</label>
                    <div className="input-wrapper">
                        <i className="fas fa-envelope input-icon"></i>
                        <input
                            name="email"
                            type="email"
                            required
                            value={formData.email}
                            onChange={handleChange}
                            className="app-input"
                            placeholder="name@company.com"
                        />
                    </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                        <label className="form-label">Heslo</label>
                        <div className="input-wrapper relative">
                            <i className="fas fa-lock input-icon"></i>
                            <input
                                name="password"
                                type={showPassword ? "text" : "password"}
                                required
                                value={formData.password}
                                onChange={handleChange}
                                className="app-input pr-10"
                                placeholder="••••••••"
                            />
                            <button
                                type="button"
                                onClick={() => setShowPassword(!showPassword)}
                                className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-blue-600 dark:hover:text-blue-400 transition-colors focus:outline-none"
                                aria-label={showPassword ? "Skryť heslo" : "Zobraziť heslo"}
                            >
                                <i className={`fas ${showPassword ? 'fa-eye-slash' : 'fa-eye'}`}></i>
                            </button>
                        </div>
                    </div>
                    <div>
                        <label className="form-label">Potvrdiť heslo</label>
                        <div className="input-wrapper relative">
                            <i className="fas fa-lock input-icon"></i>
                            <input
                                name="confirmPassword"
                                type={showConfirmPassword ? "text" : "password"}
                                required
                                value={formData.confirmPassword}
                                onChange={handleChange}
                                className={`app-input pr-10 ${isTypingConfirm ? (passwordsMatch ? 'border-green-500 focus:border-green-500 focus:ring-green-200 dark:focus:ring-green-900/40' : 'border-red-500 focus:border-red-500 focus:ring-red-200 dark:focus:ring-red-900/40') : ''}`}
                                placeholder="••••••••"
                            />
                            <button
                                type="button"
                                onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                                className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-blue-600 dark:hover:text-blue-400 transition-colors focus:outline-none"
                                aria-label={showConfirmPassword ? "Skryť heslo" : "Zobraziť heslo"}
                            >
                                <i className={`fas ${showConfirmPassword ? 'fa-eye-slash' : 'fa-eye'}`}></i>
                            </button>
                        </div>
                        {isTypingConfirm && (
                            <div
                                className={`text-xs mt-1.5 font-medium flex items-center gap-1.5 ${passwordsMatch ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
                                <i className={`fas ${passwordsMatch ? 'fa-check-circle' : 'fa-times-circle'}`}></i>
                                {passwordsMatch ? 'Heslá sa zhodujú' : 'Heslá sa nezhodujú'}
                            </div>
                        )}
                    </div>
                </div>

                <div className="pt-4">
                    <button
                        type="submit"
                        disabled={loading}
                        className="btn btn-primary w-full py-3.5 text-base shadow-lg shadow-blue-600/20 hover:shadow-blue-600/30 transition-all"
                    >
                        {loading ? (
                            <>
                                <i className="fas fa-spinner animate-spin mr-2"></i> Vytváram účet...
                            </>
                        ) : 'Vytvoriť účet'}
                    </button>
                    <p className="text-xs text-center text-gray-500 mt-4 px-4">
                        Kliknutím na tlačidlo súhlasíte s <a href="#" className="text-blue-600 hover:underline">podmienkami
                        používania</a> a spracovaním osobných údajov.
                    </p>
                </div>
            </form>

            <div className="mt-6 pt-6 border-t border-gray-100 dark:border-slate-800 text-center">
                <p className="text-gray-500 dark:text-gray-400 text-sm">
                    Už máte účet?{' '}
                    <button onClick={() => navigate(ROUTES.LOGIN)}
                            className="text-blue-600 dark:text-blue-400 font-bold hover:underline transition-colors">
                        Prihláste sa
                    </button>
                </p>
            </div>
        </AuthLayout>
    );
};
