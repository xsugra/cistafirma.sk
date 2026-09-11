export const API_BASE_URL: string =
  (typeof process !== 'undefined' && process.env.REACT_APP_API_URL)
    ? process.env.REACT_APP_API_URL
    : '/api';

export const ENABLE_MOCK_DATA = false;

export const ROUTES = {
  HOME: '/',
  MONITORING: '/monitoring',
  COMPANY: '/firma',
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

/**
 * `/firma/:ico` shows the overview, `/firma/:ico/:sekcia` a named section.
 *
 * Both halves of the URL are built here rather than at each call site, because
 * a link written by hand in one place drifts from the route declared in
 * `App.tsx` and the drift is invisible until someone clicks it.
 */
export const companyPath = (ico: string, section?: string): string =>
  section ? `${ROUTES.COMPANY}/${ico}/${section}` : `${ROUTES.COMPANY}/${ico}`;
