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
  PROFILE: '/profile',
  API_DOCS: '/api-docs',
  ADMIN: '/admin',
  NOT_FOUND: '/404',
} as const;

export type RouteKey = keyof typeof ROUTES;
