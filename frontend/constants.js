// API Configuration
// Use environment variable if available (Vite uses import.meta.env, Create React App uses process.env)
// We provide a fallback to localhost:8000 for local Django development
export const API_BASE_URL = (typeof process !== 'undefined' && process.env.REACT_APP_API_URL)
    ? process.env.REACT_APP_API_URL
    : '/api';

export const API_TIMEOUT = 10000; // Increased to 10s for slower cold starts

// Feature Flags
// Set this to TRUE to bypass backend errors and preview the design with fake data
export const ENABLE_MOCK_DATA = false;

// Routes/Navigation Keys
export const ROUTES = {
    HOME: 'home',
    MONITORING: 'monitoring',
    BLOG: 'blog',
    ABOUT: 'about',
    PRIVACY: 'privacy',
    TERMS: 'terms',
    CONTACT: 'contact',
    LOGIN: 'login',
    REGISTER: 'register',
    PRICING: 'pricing',
    PROFILE: 'profile',
    NOT_FOUND: '404'
};

// Pricing Configuration
export const PRICING_PLANS = [
    {
        id: 'free',
        name: 'Free',
        price: 0,
        features: ['Základné overenie IČO', 'Obmedzené detaily dlhov', '10 vyhľadávaní mesačne'],
        isPopular: false,
        buttonText: 'Začať zadarmo'
    },
    {
        id: 'plus',
        name: 'Plus',
        price: 19,
        features: ['Všetko z Free', 'Detailný prehľad dlhov', 'História financií (3 roky)', '50 vyhľadávaní mesačne', 'PDF Export'],
        isPopular: true,
        buttonText: 'Vybrať Plus'
    },
    {
        id: 'pro',
        name: 'Pro',
        price: 49,
        features: ['Všetko z Pro', 'Neobmedzené vyhľadávanie', 'AI Analýza rizík', 'Prepojenia osôb', 'Prioritná podpora', 'API prístup (100 volaní)'],
        isPopular: false,
        buttonText: 'Vybrať Pro'
    },
    {
        id: 'business',
        name: 'Business',
        price: 99,
        features: ['Všetko z Pro', 'API prístup (neobmedzene)', 'Hromadné overovanie', 'Vlastný account manager', 'SLA garancia'],
        isPopular: false,
        buttonText: 'Kontaktovať obchod'
    }
];
