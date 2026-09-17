import React, {useState} from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import {api} from '../api';
import {useAuth} from '../context/AuthContext';
import {AuthLayout} from '../components/AuthLayout';
import {ROUTES} from '../constants';
import {postAuthDestination} from '../utils/postAuthDestination';

export const Login: React.FC = () => {
    const navigate = useNavigate();
    const location = useLocation();
    const {login} = useAuth();
    const [identifier, setIdentifier] = useState('');
    const [password, setPassword] = useState('');
    const [showPassword, setShowPassword] = useState(false);
    // Ticked by default: the box decides whether the session outlives the tab,
    // and a reader who has to sign in again every morning is the complaint this
    // answers. Unticking it is a real choice with a real effect -- see
    // `tokenStore`, which puts an unticked session in `sessionStorage`.
    const [remember, setRemember] = useState(true);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setLoading(true);
        setError('');
        try {
            const data = await api.login(identifier, password);
            login(data.user, {access: data.token, refresh: data.refresh}, remember);
            navigate(postAuthDestination(location.state), {replace: true});
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
                    <label className="form-label" htmlFor="login-identifier">Email alebo používateľské meno</label>
                    <div className="input-wrapper">
                        <i className="fas fa-user input-icon"></i>
                        {/* `id`/`name`/`autoComplete` together: Chrome refuses to
                            autofill a field without an id or a name, and says so
                            in the console. The name is what the browser keys the
                            saved credential on, so it is also what makes the
                            password manager fill this form at all. */}
                        <input
                            id="login-identifier"
                            name="identifier"
                            type="text"
                            required
                            autoComplete="username"
                            value={identifier}
                            onChange={(e) => setIdentifier(e.target.value)}
                            className="app-input"
                            placeholder="jozef@firma.sk"
                        />
                    </div>
                </div>

                <div className="form-group">
                    <div className="flex justify-between items-center mb-1">
                        <label className="form-label mb-0" htmlFor="login-password">Heslo</label>
                        <button type="button" onClick={() => alert('Funkcia obnovy hesla bude čoskoro dostupná.')}
                                className="text-xs text-blue-600 hover:text-blue-700 font-medium">Zabudli ste?
                        </button>
                    </div>
                    <div className="input-wrapper relative">
                        <i className="fas fa-lock input-icon"></i>
                        <input
                            id="login-password"
                            name="password"
                            type={showPassword ? "text" : "password"}
                            required
                            autoComplete="current-password"
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
                    {/* The box wraps the input, so the text is its label and the
                        whole line is the click target. It carries the same
                        wording as before and now means something: ticked, the
                        session goes to `localStorage` and outlives the browser;
                        unticked, to `sessionStorage` and ends with the tab. */}
                    <label
                        className="flex items-center text-gray-600 dark:text-gray-400 cursor-pointer select-none group">
                        <input type="checkbox"
                               id="login-remember"
                               name="remember"
                               checked={remember}
                               onChange={(e) => setRemember(e.target.checked)}
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
                        onClick={() =>
                            navigate(ROUTES.REGISTER, { state: location.state })
                        }
                        className="text-blue-600 dark:text-blue-400 font-bold hover:underline transition-colors"
                    >
                        Zaregistrujte sa zadarmo
                    </button>
                </p>
            </div>
        </AuthLayout>
    );
};
