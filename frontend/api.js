import {mockCompanyData} from './mockData';
import {API_BASE_URL, ENABLE_MOCK_DATA} from './constants';

/**
 * API Wrapper for Django Backend
 * Handles Authentication, Error Parsing, and Standardization.
 */

// Dictionary for translating common Django errors to Slovak
const ERROR_TRANSLATIONS = {
    "user with this email address already exists.": "Používateľ s týmto emailom už existuje.",
    "user with this username already exists.": "Používateľ s týmto menom už existuje.",
    "This field may not be blank.": "Toto pole nesmie byť prázdne.",
    "Enter a valid email address.": "Zadajte platnú emailovú adresu.",
    "Invalid username/password.": "Nesprávne meno alebo heslo.",
    "No active account found with the given credentials": "Účet s týmito údajmi neexistuje."
};

// Helper: Parse Django DRF Errors into a single string
const parseErrors = async (response) => {
    try {
        // First get text to handle both JSON and HTML/Text responses safely
        const text = await response.text();

        let data;
        try {
            data = JSON.parse(text);
        } catch (e) {
            // If response is not JSON (e.g., Django CSRF HTML error page or 500 Server Error)
            if (response.status === 403) {
                // Specific handling for "Origin checking failed" which is the user's current issue
                if (text.includes('Origin checking failed')) {
                    return 'Django Konfigurácia: Pridajte "http://localhost:5173" do poľa CSRF_TRUSTED_ORIGINS v settings.py.';
                }
                if (text.includes('CSRF') || text.includes('Forbidden')) {
                    return 'Chyba servera: CSRF overenie zlyhalo. Skontrolujte nastavenia CORS a CSRF na backende.';
                }
            }
            // Return raw text excerpt if it's not JSON
            return text.slice(0, 150) || `HTTP Error: ${response.status}`;
        }

        // Case 1: SimpleJWT specific error structure
        if (data.code === 'token_not_valid') {
            return 'Platnosť prihlásenia vypršala.';
        }

        // Case 2: Standard DRF 'detail' (e.g. Authentication Failed)
        if (data.detail) return data.detail;

        // Case 3: Validation errors dictionary (e.g. { email: ["Invalid"], password: ["Too short"] })
        if (typeof data === 'object') {
            const messages = Object.entries(data)
                .map(([key, val]) => {
                    // Skip technical fields
                    if (key === 'code' || key === 'messages') return null;

                    // Format Field Name (e.g. first_name -> First Name)
                    // Remove underscores for nicer display
                    const cleanKey = key.replace(/_/g, ' ');
                    const fieldName = cleanKey.charAt(0).toUpperCase() + cleanKey.slice(1);

                    let errorMsg = Array.isArray(val) ? val.join(' ') : val;

                    // Translate common English Django errors
                    if (ERROR_TRANSLATIONS[errorMsg]) {
                        errorMsg = ERROR_TRANSLATIONS[errorMsg];
                    }

                    return `${fieldName}: ${errorMsg}`;
                })
                .filter(Boolean)
                .join(' | '); // Separator for multiple field errors
            return messages || 'Neznáma chyba servera.';
        }
        return 'Neznáma chyba servera.';
    } catch (e) {
        return `HTTP Error: ${response.status}`;
    }
};

// Internal Request Wrapper
const request = async (endpoint, options = {}) => {
    const token = localStorage.getItem('token');
    const headers = {
        'Content-Type': 'application/json',
        ...(token ? {'Authorization': `Bearer ${token}`} : {}),
        ...options.headers,
    };

    const config = {
        ...options,
        headers,
    };

    try {
        const response = await fetch(`${API_BASE_URL}${endpoint}`, config);

        // Handle 401 Unauthorized (Token Expired/Invalid)
        if (response.status === 401) {
            // CRITICAL: Clear the invalid token immediately to prevent infinite loops
            localStorage.removeItem('token');

            // Dispatch custom event so AuthContext can catch it and update state
            window.dispatchEvent(new CustomEvent('auth:unauthorized'));
            throw new Error('Platnosť prihlásenia vypršala. Prihláste sa prosím znova.');
        }

        if (!response.ok) {
            const errorMessage = await parseErrors(response);
            throw new Error(errorMessage);
        }

        // Return empty object for 204 No Content, else JSON
        if (response.status === 204) return {};
        return response.json();

    } catch (error) {
        // Handle Network Errors (CORS, Server Down)
        if (error instanceof TypeError && error.message === 'Failed to fetch') {
            throw new Error('Nepodarilo sa pripojiť k serveru. Skontrolujte CORS nastavenia (povolený port 5173) alebo či server beží.');
        }
        // Network errors or parsed backend errors
        throw error;
    }
};

// Helper to map Django snake_case to React camelCase (INCOMING from Backend)
const mapUserResponse = (data) => {
    return {
        id: data.id,
        email: data.email,
        username: data.username,
        // Backend returns first_name, frontend needs firstName
        firstName: data.first_name || '',
        lastName: data.last_name || '',
        // Backend returns subscription_plan, frontend needs plan
        plan: data.subscription_plan || 'free',
        // Fallbacks if backend doesn't send usage data yet
        apiCallsUsed: data.api_calls_used || 0,
        apiCallsLimit: data.api_calls_limit || 10
    };
};

// Helper to map React camelCase to Django snake_case (OUTGOING to Backend)
const mapUserPayload = (data) => {
    const payload = {};
    if (data.email !== undefined) payload.email = data.email;
    if (data.username !== undefined) payload.username = data.username;
    if (data.password !== undefined) payload.password = data.password;

    // Transform camelCase to snake_case
    if (data.firstName !== undefined) payload.first_name = data.firstName;
    if (data.lastName !== undefined) payload.last_name = data.lastName;

    return payload;
};

export const api = {
    /**
     * Fetch landing page statistics
     */
    getLandingStats: async () => {
        if (ENABLE_MOCK_DATA) {
            return new Promise((resolve) => setTimeout(() => resolve({
                companiesIndexed: 1250000,
                dailyChecks: 45000,
                riskyCompaniesDetected: 120
            }), 500));
        }
        return request('/stats/landing/');
    },

    /**
     * Fetch company details by ICO
     */
    getCompany: async (ico) => {
        if (ENABLE_MOCK_DATA) {
            return new Promise((resolve, reject) => {
                setTimeout(() => {
                    if (ico === '50059959') {
                        resolve(mockCompanyData);
                    } else if (ico === '12345678') {
                        resolve({
                            ...mockCompanyData,
                            ico: '12345678',
                            name: 'Stará Firma, a.s.',
                            status: 'V likvidácii',
                            riskScore: {score: 90, summary: 'Vysoké riziko.', calculationDate: new Date().toISOString()}
                        });
                    } else if (ico.length !== 8) {
                        reject(new Error("IČO musí mať 8 číslic."));
                    } else {
                        // Dynamic mock fallback
                        resolve({
                            ...mockCompanyData,
                            ico: ico,
                            name: `Mock Firma ${ico}`,
                            status: 'Aktívna',
                            riskScore: {
                                score: Math.floor(Math.random() * 100),
                                summary: 'Automaticky generovaný mock.',
                                calculationDate: new Date().toISOString()
                            }
                        });
                    }
                }, 600);
            });
        }
        return request(`/companies/${ico}/`);
    },

    /**
     * User Login
     */
    login: async (identifier, password) => {
        if (ENABLE_MOCK_DATA) {
            return new Promise((resolve) => {
                setTimeout(() => {
                    localStorage.setItem('token', 'mock-jwt-token-12345');
                    resolve({
                        token: 'mock-jwt-token-12345',
                        user: {
                            id: 'u1',
                            email: 'jozef@example.com',
                            username: 'jmrkvicka',
                            firstName: 'Jozef',
                            lastName: 'Mrkvička',
                            plan: 'plus',
                            apiCallsUsed: 34,
                            apiCallsLimit: 50
                        }
                    });
                }, 1000)
            });
        }

        // 1. Authenticate and get Token
        const tokenResponse = await request('/auth/token/', {
            method: 'POST',
            body: JSON.stringify({email: identifier, password: password})
        });

        const accessToken = tokenResponse.access || tokenResponse.token;

        if (!accessToken) {
            throw new Error("Server nevrátil prístupový token. Skontrolujte odpoveď backendu.");
        }

        // 2. Fetch User Profile
        const rawUserProfile = await request('/auth/profile/', {
            headers: {
                'Authorization': `Bearer ${accessToken}`
            }
        });

        // 3. Map Response and Return
        return {
            token: accessToken,
            user: mapUserResponse(rawUserProfile)
        };
    },

    /**
     * User Registration
     */
    register: async (userData) => {
        if (ENABLE_MOCK_DATA) {
            return new Promise((resolve) => setTimeout(() => resolve({success: true}), 1500));
        }

        // Use mapping helper to convert firstName -> first_name
        const payload = mapUserPayload(userData);

        return request('/auth/register/', {
            method: 'POST',
            body: JSON.stringify(payload)
        });
    },

    /**
     * Get User Profile (Full Details)
     */
    getProfile: async () => {
        if (ENABLE_MOCK_DATA) {
            return new Promise((resolve) => setTimeout(() => resolve({
                id: 'u1',
                firstName: 'Jozef',
                lastName: 'Mrkvička',
                username: 'jmrkvicka',
                email: 'jozef@example.com',
                plan: 'plus',
                apiCallsUsed: 34,
                apiCallsLimit: 50
            }), 600));
        }
        const rawData = await request('/auth/profile/');
        return mapUserResponse(rawData);
    },

    /**
     * Update User Profile
     */
    updateProfile: async (data) => {
        if (ENABLE_MOCK_DATA) {
            return new Promise((resolve) => setTimeout(() => resolve(data), 1000));
        }

        // Use mapping helper to convert firstName -> first_name
        const payload = mapUserPayload(data);

        const rawData = await request('/auth/profile/', {
            method: 'PATCH',
            body: JSON.stringify(payload)
        });
        return mapUserResponse(rawData);
    },

    /**
     * Change Password
     */
    changePassword: async (oldPassword, newPassword) => {
        if (ENABLE_MOCK_DATA) {
            return new Promise((resolve) => setTimeout(() => resolve({success: true}), 1000));
        }
        return request('/auth/change-password/', {
            method: 'POST',
            body: JSON.stringify({old_password: oldPassword, new_password: newPassword})
        });
    },

    /**
     * Get User Watchlist
     */
    getWatchlist: async () => {
        if (ENABLE_MOCK_DATA) {
            return new Promise((resolve) => setTimeout(() => resolve([
                {
                    id: 'w1',
                    ico: '50059959',
                    name: 'Quantum Solutions s. r. o.',
                    status: 'Aktívna',
                    riskScore: 68,
                    addedAt: '2024-01-15'
                },
                {
                    id: 'w2',
                    ico: '12345678',
                    name: 'Stará Firma, a.s.',
                    status: 'V likvidácii',
                    riskScore: 90,
                    addedAt: '2023-11-20'
                },
                {
                    id: 'w3',
                    ico: '87654321',
                    name: 'Tech Startup s.r.o.',
                    status: 'Aktívna',
                    riskScore: 12,
                    addedAt: '2024-02-01'
                }
            ]), 800));
        }
        return request('/watchlist/');
    },

    /**
     * Add to Watchlist
     */
    addToWatchlist: async (ico) => {
        if (ENABLE_MOCK_DATA) {
            return new Promise((resolve) => setTimeout(() => resolve({success: true}), 600));
        }
        return request('/watchlist/', {
            method: 'POST',
            body: JSON.stringify({ico})
        });
    },

    /**
     * Remove from Watchlist
     */
    removeFromWatchlist: async (id) => {
        if (ENABLE_MOCK_DATA) {
            return new Promise((resolve) => setTimeout(() => resolve({success: true}), 600));
        }
        return request(`/watchlist/${id}/`, {
            method: 'DELETE'
        });
    },

    /**
     * Get User Search History
     */
    getHistory: async () => {
        if (ENABLE_MOCK_DATA) {
            return new Promise((resolve) => setTimeout(() => resolve([
                {id: 'h1', ico: '50059959', name: 'Quantum Solutions s. r. o.', searchedAt: '2024-02-10T14:30:00'},
                {id: 'h2', ico: '33322211', name: 'Stavebniny XY', searchedAt: '2024-02-09T09:15:00'},
                {id: 'h3', ico: '11111111', name: 'Neznáma firma', searchedAt: '2024-02-08T18:45:00'}
            ]), 800));
        }
        return request('/history/');
    }
};
