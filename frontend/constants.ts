export const API_BASE_URL: string =
  (typeof process !== 'undefined' && process.env.REACT_APP_API_URL)
    ? process.env.REACT_APP_API_URL
    : '/api';

export const ENABLE_MOCK_DATA = false;

export const ROUTES = {
  HOME: '/',
  MONITORING: '/monitoring',
  BLOG: '/blog',
  ABOUT: '/about',
  PRIVACY: '/privacy',
  TERMS: '/terms',
  CONTACT: '/contact',
  LOGIN: '/login',
  REGISTER: '/register',
  PRICING: '/pricing',
  PROFILE: '/profile',
  API_DOCS: '/api-docs',
  ADMIN: '/admin',
  NOT_FOUND: '/404',
} as const;

export type RouteKey = keyof typeof ROUTES;

export interface PricingPlan {
  id: string;
  name: string;
  price: number;
  features: string[];
  isPopular: boolean;
  buttonText: string;
}

export const PRICING_PLANS: PricingPlan[] = [
  {
    id: 'free',
    name: 'Free',
    price: 0,
    features: ['Základné overenie IČO', 'Obmedzené detaily dlhov', '10 vyhľadávaní mesačne'],
    isPopular: false,
    buttonText: 'Začať zadarmo',
  },
  {
    id: 'plus',
    name: 'Plus',
    price: 19,
    features: ['Všetko z Free', 'Detailný prehľad dlhov', 'História financií (3 roky)', '50 vyhľadávaní mesačne', 'PDF Export'],
    isPopular: true,
    buttonText: 'Vybrať Plus',
  },
  {
    id: 'pro',
    name: 'Pro',
    price: 49,
    features: ['Všetko z Pro', 'Neobmedzené vyhľadávanie', 'Analýza rizík', 'Prepojenia osôb', 'Prioritná podpora', 'API prístup (100 volaní)'],
    isPopular: false,
    buttonText: 'Vybrať Pro',
  },
  {
    id: 'business',
    name: 'Business',
    price: 99,
    features: ['Všetko z Pro', 'API prístup (neobmedzene)', 'Hromadné overovanie', 'Vlastný account manager', 'SLA garancia'],
    isPopular: false,
    buttonText: 'Kontaktovať obchod',
  },
];
