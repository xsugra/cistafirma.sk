import React, {useState} from 'react';
import { useNavigate } from 'react-router-dom';
import {api} from '../api';
import {useAuth} from '../context/AuthContext';
import {AuthLayout} from '../components/AuthLayout';
import {ROUTES} from '../constants';

export const Login: React.FC = () => {
    const navigate = useNavigate();
    const {login} = useAuth();
    const [identifier, setIdentifier] = useState('');
    const [password, setPassword] = useState('');
    const [showPassword, setShowPassword] = useState(false);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setLoading(true);
        setError('');
        try {
            const data: any = await api.login(identifier, password);
            login(data.user, data.token);
            navigate(ROUTES.HOME);
        } catch (err: any) {
            setError(err.message || 'Prihlásenie zlyhalo. Skontrolujte svoje údaje.');
        } finally {
            setLoading(false);
        }
    };

    return (
        <AuthLayout
            title="Vitajte späť"
            subtitle="Prihláste sa do svojho účtu a pokračujte v práci."
        >
            {error && (
                <div
                    className="mb-6 p-4 bg-red-50 dark:bg-red-900/20 border-l-4 border-red-500 text-red-700 dark:text-red-300 text-sm rounded-r-lg flex items-start gap-3">
                    <i className="fas fa-exclamation-circle flex-shrink-0 mt-0.5"></i>
                    <span className="text-left leading-relaxed">{error}</span>
                </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-5">
                <div className="form-group">
                    <label className="form-label">Email alebo používateľské meno</label>
                    <div className="input-wrapper">
                        <i className="fas fa-user input-icon"></i>
                        <input
                            type="text"
                            required
                            value={identifier}
                            onChange={(e) => setIdentifier(e.target.value)}
                            className="app-input"
                            placeholder="jozef@firma.sk"
                        />
                    </div>
                </div>

                <div className="form-group">
                    <div className="flex justify-between items-center mb-1">
                        <label className="form-label mb-0">Heslo</label>
                        <button type="button" onClick={() => alert('Funkcia obnovy hesla bude čoskoro dostupná.')}
                                className="text-xs text-blue-600 hover:text-blue-700 font-medium">Zabudli ste?
                        </button>
                    </div>
                    <div className="input-wrapper relative">
                        <i className="fas fa-lock input-icon"></i>
                        <input
                            type={showPassword ? "text" : "password"}
                            required
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
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

                <div className="flex items-center text-sm mb-2">
                    <label
                        className="flex items-center text-gray-600 dark:text-gray-400 cursor-pointer select-none group">
                        <input type="checkbox"
                               className="mr-2 w-4 h-4 rounded border-gray-300 dark:border-slate-600 text-blue-600 focus:ring-blue-500 transition-colors"/>
                        <span className="group-hover:text-gray-800 dark:group-hover:text-gray-200 transition-colors">Zapamätať prihlásenie</span>
                    </label>
                </div>

                <button
                    type="submit"
                    disabled={loading}
                    className="btn btn-primary w-full py-3.5 text-base shadow-lg shadow-blue-600/20 hover:shadow-blue-600/30 transition-all"
                >
                    {loading ? (
                        <>
                            <i className="fas fa-spinner animate-spin mr-2"></i> Overujem...
                        </>
                    ) : (
                        <>
                            Prihlásiť sa <i
                            className="fas fa-arrow-right ml-2 group-hover:translate-x-1 transition-transform"></i>
                        </>
                    )}
                </button>
            </form>

            <div className="mt-8 pt-6 border-t border-gray-100 dark:border-slate-800 text-center">
                <p className="text-gray-500 dark:text-gray-400 text-sm">
                    Ešte nemáte účet?{' '}
                    <button
                        onClick={() => navigate(ROUTES.REGISTER)}
                        className="text-blue-600 dark:text-blue-400 font-bold hover:underline transition-colors"
                    >
                        Zaregistrujte sa zadarmo
                    </button>
                </p>
            </div>
        </AuthLayout>
    );
};
