import { API_BASE_URL } from '../constants';

const ERROR_TRANSLATIONS: Record<string, string> = {
  'user with this email address already exists.': 'Používateľ s týmto emailom už existuje.',
  'user with this username already exists.': 'Používateľ s týmto menom už existuje.',
  'This field may not be blank.': 'Toto pole nesmie byť prázdne.',
  'Enter a valid email address.': 'Zadajte platnú emailovú adresu.',
  'Invalid username/password.': 'Nesprávne meno alebo heslo.',
  'No active account found with the given credentials': 'Účet s týmito údajmi neexistuje.',
};

async function parseErrors(response: Response): Promise<string> {
  try {
    const text = await response.text();
    let data: any;
    try {
      data = JSON.parse(text);
    } catch {
      if (response.status === 403) {
        if (text.includes('Origin checking failed')) {
          return 'Django Konfigurácia: Pridajte frontend origin do CSRF_TRUSTED_ORIGINS.';
        }
        if (text.includes('CSRF') || text.includes('Forbidden')) {
          return 'Chyba servera: CSRF overenie zlyhalo.';
        }
      }
      return text.slice(0, 150) || `HTTP Error: ${response.status}`;
    }

    if (data.code === 'token_not_valid') return 'Platnosť prihlásenia vypršala.';
    if (data.detail) return data.detail;

    if (typeof data === 'object') {
      const messages = Object.entries(data)
        .map(([key, val]) => {
          if (key === 'code' || key === 'messages') return null;
          const fieldName = key.replace(/_/g, ' ').replace(/^\w/, (c) => c.toUpperCase());
          let errorMsg = Array.isArray(val) ? val.join(' ') : String(val);
          if (ERROR_TRANSLATIONS[errorMsg]) errorMsg = ERROR_TRANSLATIONS[errorMsg];
          return `${fieldName}: ${errorMsg}`;
        })
        .filter(Boolean)
        .join(' | ');
      return messages || 'Neznáma chyba servera.';
    }
    return 'Neznáma chyba servera.';
  } catch {
    return `HTTP Error: ${response.status}`;
  }
}

export async function apiRequest<T>(
  endpoint: string,
  options: RequestInit = {},
  baseUrl: string = API_BASE_URL,
): Promise<T> {
  const token = localStorage.getItem('token');
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...((options.headers as Record<string, string>) || {}),
  };

  const response = await fetch(`${baseUrl}${endpoint}`, { ...options, headers });

  if (response.status === 401) {
    localStorage.removeItem('token');
    window.dispatchEvent(new CustomEvent('auth:unauthorized'));
    throw new Error('Platnosť prihlásenia vypršala. Prihláste sa prosím znova.');
  }

  if (!response.ok) {
    const errorMessage = await parseErrors(response);
    throw new Error(errorMessage);
  }

  if (response.status === 204) return {} as T;
  return response.json();
}
