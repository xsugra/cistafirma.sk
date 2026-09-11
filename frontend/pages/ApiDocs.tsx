import React, { useState, useRef, useEffect } from 'react';

type HttpMethod = 'GET' | 'POST' | 'PATCH' | 'DELETE';

interface Endpoint {
  method: HttpMethod;
  path: string;
  description: string;
  auth?: boolean;
  request?: string;
  response?: string;
  responseCode?: number;
  params?: { name: string; type: string; description: string }[];
}

interface Section {
  id: string;
  title: string;
  icon: string;
  description?: string;
  endpoints: Endpoint[];
}

const METHOD_COLORS: Record<HttpMethod, string> = {
  GET: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400',
  POST: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
  PATCH: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400',
  DELETE: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
};

const SECTIONS: Section[] = [
  {
    id: 'auth',
    title: 'Autentifikácia',
    icon: 'fa-key',
    description: 'JWT Bearer token v Authorization headeri. Token sa ukladá do localStorage.',
    endpoints: [
      {
        method: 'POST',
        path: '/api/auth/register/',
        description: 'Registrácia nového používateľa.',
        request: `{
  "email": "user@example.com",
  "username": "novak",
  "password": "securePassword123",
  "first_name": "Ján",
  "last_name": "Novák"
}`,
        response: `{ "success": true }`,
        responseCode: 201,
      },
      {
        method: 'POST',
        path: '/api/auth/token/',
        description: 'Vydanie JWT access + refresh tokenu.',
        request: `{
  "email": "user@example.com",
  "password": "securePassword123"
}`,
        response: `{
  "access": "eyJ0eXAiOiJKV1Qi...",
  "refresh": "eyJ0eXAiOiJKV1Qi..."
}`,
        responseCode: 200,
      },
      {
        method: 'POST',
        path: '/api/auth/token/refresh/',
        description: 'Obnovenie expirovaného access tokenu.',
        request: `{ "refresh": "eyJ0eXAiOiJKV1Qi..." }`,
        response: `{ "access": "eyJ0eXAiOiJKV1Qi..." }`,
        responseCode: 200,
      },
      {
        method: 'GET',
        path: '/api/auth/profile/',
        description: 'Profil aktuálne prihláseného používateľa.',
        auth: true,
        response: `{
  "id": "1",
  "email": "user@example.com",
  "username": "novak",
  "first_name": "Ján",
  "last_name": "Novák",
  "subscription_plan": "plus",
  "api_calls_used": 34,
  "api_calls_limit": 50,
  "is_staff": false,
  "is_superuser": false
}`,
        responseCode: 200,
      },
      {
        method: 'PATCH',
        path: '/api/auth/profile/',
        description: 'Úprava profilu. Posiela len zmenené polia.',
        auth: true,
        request: `{
  "first_name": "Ján",
  "last_name": "Novák"
}`,
        responseCode: 200,
      },
      {
        method: 'POST',
        path: '/api/auth/change-password/',
        description: 'Zmena hesla.',
        auth: true,
        request: `{
  "old_password": "staréHeslo",
  "new_password": "novéHeslo123"
}`,
        response: `{ "success": true }`,
        responseCode: 200,
      },
    ],
  },
  {
    id: 'companies',
    title: 'Firmy',
    icon: 'fa-building',
    description: 'Vyhľadávanie a detail firiem podľa IČO.',
    endpoints: [
      {
        method: 'GET',
        path: '/api/companies/search/',
        description: 'Fulltextové vyhľadávanie podľa IČO alebo názvu firmy.',
        params: [
          { name: 'q', type: 'string', description: 'Hľadaný výraz (IČO alebo prefix názvu)' },
        ],
        response: `{
  "results": [
    {
      "id": 1234,
      "ico": "31560636",
      "nazov_UJ": "Tatry mountain resorts, a.s.",
      "mesto": "Liptovský Mikuláš",
      "ulica": "Demänovská Dolina 72",
      "psc": "03104",
      "legal_form": "Akciová spoločnosť",
      "datum_zalozenia": "1992-11-10",
      "datum_zrusenia": null
    }
  ]
}`,
        responseCode: 200,
      },
      {
        method: 'GET',
        path: '/api/companies/:ico/',
        description: 'Detail firmy podľa IČO. Obsahuje finančné dáta, exekutívu, ORSR profil, dlhy, DPH status.',
        response: `{
  "ico": "31560636",
  "nazov_UJ": "Tatry mountain resorts, a.s.",
  "legal_form": "Akciová spoločnosť",
  "datum_zalozenia": "1992-11-10",
  "mesto": "Liptovský Mikuláš",
  "debt_vszp": 0,
  "debt_soc_poist": 0,
  "tax_debt": 0,
  "vat_payer": true,
  "tax_reliability": "spoľahlivý",
  "financials": [...],
  "executives": [...],
  "connections": [...],
  "orsr_profile": {...}
}`,
        responseCode: 200,
      },
    ],
  },
  {
    id: 'graph',
    title: 'Graf prepojení',
    icon: 'fa-project-diagram',
    description: 'Graf osôb a firiem prepojených cez spoločné osoby.',
    endpoints: [
      {
        method: 'GET',
        path: '/api/companies/:ico/graph/',
        description: 'Graf prepojení z pohľadu firmy.',
        response: `{
  "nodes": [
    {
      "id": "company_31560636",
      "type": "company",
      "label": "TMR, a.s.",
      "ico": "31560636",
      "status": "Aktívna"
    },
    {
      "id": "person_123",
      "type": "person",
      "label": "Ing. Ján Novák",
      "rolesCount": 3
    }
  ],
  "edges": [
    {
      "source": "person_123",
      "target": "company_31560636",
      "role": "Konateľ",
      "isActive": true
    }
  ],
  "meta": {
    "center_node": "company_31560636",
    "depth": 2,
    "total_nodes": 11,
    "truncated": false
  }
}`,
        responseCode: 200,
      },
      {
        method: 'GET',
        path: '/api/persons/:id/graph/',
        description: 'Graf prepojení z pohľadu osoby. Rovnaký formát odpovede.',
        responseCode: 200,
      },
      {
        method: 'GET',
        path: '/api/persons/:id/',
        description: 'Detail osoby.',
        responseCode: 200,
      },
    ],
  },
  {
    id: 'watchlist',
    title: 'Watchlist',
    icon: 'fa-eye',
    description: 'Sledovanie firiem. Vyžaduje JWT.',
    endpoints: [
      {
        method: 'GET',
        path: '/api/watchlist/',
        description: 'Zoznam sledovaných firiem.',
        auth: true,
        response: `[
  {
    "id": "w1",
    "ico": "50059959",
    "name": "Quantum Solutions s. r. o.",
    "status": "Aktívna",
    "riskScore": 68,
    "addedAt": "2024-01-15"
  }
]`,
        responseCode: 200,
      },
      {
        method: 'POST',
        path: '/api/watchlist/',
        description: 'Pridanie firmy do watchlistu.',
        auth: true,
        request: `{ "ico": "31560636" }`,
        response: `{ "success": true }`,
        responseCode: 201,
      },
      {
        method: 'DELETE',
        path: '/api/watchlist/:id/',
        description: 'Odstránenie z watchlistu.',
        auth: true,
        responseCode: 204,
      },
    ],
  },
  {
    id: 'stats',
    title: 'Štatistiky',
    icon: 'fa-chart-bar',
    endpoints: [
      {
        method: 'GET',
        path: '/api/stats/landing/',
        description: 'Štatistiky pre landing page. Nevyžaduje autentifikáciu.',
        response: `{
  "companiesIndexed": 1250000,
  "dailyChecks": 45000,
  "riskyCompaniesDetected": 120
}`,
        responseCode: 200,
      },
    ],
  },
  {
    id: 'admin',
    title: 'Admin API',
    icon: 'fa-shield-alt',
    description: 'Prístup obmedzený na is_staff používateľov. Vyžaduje JWT.',
    endpoints: [
      { method: 'GET', path: '/api/admin/metrics/overview/', description: 'Prehľad (firmy, sync, users)', auth: true },
      { method: 'GET', path: '/api/admin/metrics/sync/', description: 'Sync zdroje a throughput', auth: true },
      { method: 'GET', path: '/api/admin/metrics/business/', description: 'Business metriky', auth: true },
      { method: 'GET', path: '/api/admin/metrics/system/', description: 'Systémové info (DB, Redis, Celery)', auth: true },
      { method: 'GET', path: '/api/admin/companies/', description: 'Zoznam firiem (paginovaný)', auth: true },
      { method: 'GET', path: '/api/admin/users/', description: 'Zoznam používateľov', auth: true },
      { method: 'PATCH', path: '/api/admin/users/:id/', description: 'Úprava používateľa', auth: true },
      { method: 'POST', path: '/api/admin/users/:id/impersonate/', description: 'Impersonácia (superuser only)', auth: true },
      { method: 'GET', path: '/api/admin/sync/jobs/', description: 'Zoznam sync jobov', auth: true },
      {
        method: 'POST',
        path: '/api/admin/sync/jobs/',
        description: 'Spustenie nového sync jobu',
        auth: true,
        request: `{
  "job_type": "ruz_full",
  "parameters": {},
  "notes": "Manual trigger"
}`,
        responseCode: 201,
      },
      { method: 'POST', path: '/api/admin/sync/jobs/:id/pause/', description: 'Pozastavenie jobu', auth: true },
      { method: 'POST', path: '/api/admin/sync/jobs/:id/resume/', description: 'Obnovenie jobu', auth: true },
      { method: 'POST', path: '/api/admin/sync/jobs/:id/cancel/', description: 'Zrušenie jobu', auth: true },
      { method: 'POST', path: '/api/admin/sync/jobs/:id/retry-failed/', description: 'Opätovné spustenie jobu (rovnaký typ a parametre)', auth: true },
      { method: 'GET', path: '/api/admin/sync/companies/', description: 'Sync stav per firma', auth: true },
      { method: 'GET', path: '/api/admin/sync/queues/', description: 'Hĺbka Celery frontov', auth: true },
      { method: 'GET', path: '/api/admin/sync/scheduled/', description: 'Zoznam plánovaných taskov', auth: true },
      { method: 'POST', path: '/api/admin/sync/scheduled/:id/toggle/', description: 'Zapnutie/vypnutie tasku', auth: true },
      { method: 'GET', path: '/api/admin/sync/focus-mode/', description: 'Aktuálny stav focus mode', auth: true },
      { method: 'POST', path: '/api/admin/sync/focus-mode/enter/', description: 'Vstup do focus mode', auth: true },
      { method: 'POST', path: '/api/admin/sync/focus-mode/exit/', description: 'Výstup z focus mode', auth: true },
      { method: 'GET', path: '/api/admin/audit/', description: 'Zoznam audit logov (paginovaný)', auth: true },
      { method: 'GET', path: '/api/admin/system/health/', description: 'Health check (DB, Redis, workers)', auth: true },
      { method: 'GET', path: '/api/admin/system/info/', description: 'Systémové informácie', auth: true },
    ],
  },
  {
    id: 'health',
    title: 'Zdravie',
    icon: 'fa-heartbeat',
    endpoints: [
      {
        method: 'GET',
        path: '/healthz/',
        description: 'Liveness endpoint. Nevyžaduje autentifikáciu.',
        response: `{ "status": "ok" }`,
        responseCode: 200,
      },
    ],
  },
];

const AUTH_FLOW = `1. POST /api/auth/token/ → access + refresh token
2. localStorage.setItem('token', access)
3. Každý request: Authorization: Bearer <access>
4. Pri 401: localStorage.removeItem('token') + logout
5. AuthContext počúva event → automatický logout`;

const ERROR_CODES = [
  { code: 200, meaning: 'Úspešné čítanie' },
  { code: 201, meaning: 'Úspešné vytvorenie' },
  { code: 204, meaning: 'Úspešné vymazanie (bez body)' },
  { code: 400, meaning: 'Validačná chyba' },
  { code: 401, meaning: 'Neplatný/expirovaný token → automatický logout' },
  { code: 403, meaning: 'CSRF / Forbidden' },
  { code: 404, meaning: 'Nenájdené' },
  { code: 500, meaning: 'Interná chyba servera' },
];

function CodeBlock({ code, label }: { code: string; label?: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="relative group">
      {label && (
        <div className="text-[11px] font-medium text-gray-400 dark:text-gray-500 uppercase tracking-wider mb-1">
          {label}
        </div>
      )}
      <pre className="bg-gray-950 dark:bg-black text-gray-300 text-sm rounded-lg p-4 overflow-x-auto font-mono leading-relaxed border border-gray-800">
        {code}
      </pre>
      <button
        onClick={handleCopy}
        className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity px-2 py-1 rounded text-xs bg-gray-800 text-gray-400 hover:text-white"
      >
        {copied ? 'Skopírované!' : 'Kopírovať'}
      </button>
    </div>
  );
}

function MethodBadge({ method }: { method: HttpMethod }) {
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded text-xs font-bold font-mono ${METHOD_COLORS[method]}`}>
      {method}
    </span>
  );
}

function EndpointCard({ endpoint }: { endpoint: Endpoint }) {
  const [expanded, setExpanded] = useState(false);
  const hasDetails = endpoint.request || endpoint.response || endpoint.params;

  return (
    <div className="bg-white dark:bg-slate-900 shadow-sm border border-gray-200 dark:border-gray-700/50 rounded-lg overflow-hidden transition-colors hover:border-gray-300 dark:hover:border-gray-600">
      <button
        onClick={() => hasDetails && setExpanded(!expanded)}
        className={`w-full flex items-center gap-3 px-4 py-3 text-left ${hasDetails ? 'cursor-pointer' : 'cursor-default'}`}
      >
        <MethodBadge method={endpoint.method} />
        <code className="text-sm font-mono text-gray-900 dark:text-gray-100 flex-1">
          {endpoint.path}
        </code>
        {endpoint.auth && (
          <span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400">
            JWT
          </span>
        )}
        {hasDetails && (
          <i className={`fas fa-chevron-down text-xs text-gray-400 transition-transform ${expanded ? 'rotate-180' : ''}`} />
        )}
      </button>

      {expanded && (
        <div className="px-4 pb-4 space-y-3 border-t border-gray-100 dark:border-gray-800 pt-3">
          <p className="text-sm text-gray-600 dark:text-gray-400">{endpoint.description}</p>

          {endpoint.params && (
            <div>
              <div className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-1.5 uppercase tracking-wider">Parametre</div>
              <div className="space-y-1">
                {endpoint.params.map(p => (
                  <div key={p.name} className="flex items-baseline gap-2 text-sm">
                    <code className="text-blue-600 dark:text-blue-400 font-mono">{p.name}</code>
                    <span className="text-gray-400 text-xs">{p.type}</span>
                    <span className="text-gray-600 dark:text-gray-400">{p.description}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {endpoint.request && <CodeBlock code={endpoint.request} label="Request" />}
          {endpoint.response && (
            <CodeBlock
              code={endpoint.response}
              label={`Response ${endpoint.responseCode || 200}`}
            />
          )}
        </div>
      )}

      {!expanded && !hasDetails && (
        <div className="px-4 pb-3">
          <p className="text-sm text-gray-500 dark:text-gray-400">{endpoint.description}</p>
        </div>
      )}
    </div>
  );
}

export const ApiDocs: React.FC = () => {
  const [activeSection, setActiveSection] = useState('auth');
  const sectionRefs = useRef<Record<string, HTMLDivElement | null>>({});

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            setActiveSection(entry.target.id);
            break;
          }
        }
      },
      { rootMargin: '-100px 0px -60% 0px' }
    );

    Object.values(sectionRefs.current).forEach(el => {
      if (el) observer.observe(el);
    });

    return () => observer.disconnect();
  }, []);

  const scrollTo = (id: string) => {
    sectionRefs.current[id]?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  return (
    <div className="max-w-7xl mx-auto w-full animate-fade-in py-6">
      <div className="mb-10">
        <h1 className="text-3xl md:text-4xl font-bold text-gray-900 dark:text-white mb-3">
          API Dokumentácia
        </h1>
        <p className="text-gray-600 dark:text-gray-400 text-lg">
          REST API referencia pre integráciu s cistafirma.sk
        </p>
        <div className="flex flex-wrap gap-3 mt-4 text-sm text-gray-500 dark:text-gray-400">
          <span className="flex items-center gap-1.5">
            <i className="fas fa-server text-xs"></i>
            Base URL: <code className="bg-gray-100 dark:bg-gray-800 px-1.5 py-0.5 rounded font-mono text-xs">/api</code>
          </span>
          <span className="flex items-center gap-1.5">
            <i className="fas fa-lock text-xs"></i>
            Auth: JWT Bearer token
          </span>
        </div>
      </div>

      <div className="flex gap-8">
        {/* Sidebar */}
        <nav className="hidden lg:block w-56 flex-shrink-0">
          <div className="sticky top-24 space-y-0.5">
            <div className="text-[11px] font-medium text-gray-400 dark:text-gray-500 uppercase tracking-wider mb-2 px-3">
              Sekcie
            </div>
            {SECTIONS.map(section => (
              <button
                key={section.id}
                onClick={() => scrollTo(section.id)}
                className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-colors text-left ${
                  activeSection === section.id
                    ? 'bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-400 font-medium'
                    : 'text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800/50'
                }`}
              >
                <i className={`fas ${section.icon} w-4 text-center text-xs`} />
                {section.title}
                <span className="ml-auto text-xs text-gray-400 dark:text-gray-500">
                  {section.endpoints.length}
                </span>
              </button>
            ))}
            <div className="border-t border-gray-200 dark:border-gray-700 my-2" />
            <button
              onClick={() => scrollTo('auth-flow')}
              className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-colors text-left ${
                activeSection === 'auth-flow'
                  ? 'bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-400 font-medium'
                  : 'text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800/50'
              }`}
            >
              <i className="fas fa-route w-4 text-center text-xs" />
              Auth flow
            </button>
            <button
              onClick={() => scrollTo('errors')}
              className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-colors text-left ${
                activeSection === 'errors'
                  ? 'bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-400 font-medium'
                  : 'text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800/50'
              }`}
            >
              <i className="fas fa-exclamation-triangle w-4 text-center text-xs" />
              Chybové stavy
            </button>
          </div>
        </nav>

        {/* Content */}
        <div className="flex-1 min-w-0 space-y-10">
          {SECTIONS.map(section => (
            <div
              key={section.id}
              id={section.id}
              ref={el => { sectionRefs.current[section.id] = el; }}
              className="scroll-mt-24"
            >
              <div className="flex items-center gap-3 mb-1">
                <div className="w-8 h-8 rounded-lg bg-brand/10 flex items-center justify-center">
                  <i className={`fas ${section.icon} text-brand text-sm`} />
                </div>
                <h2 className="text-xl font-bold text-gray-900 dark:text-white">
                  {section.title}
                </h2>
              </div>
              {section.description && (
                <p className="text-sm text-gray-500 dark:text-gray-400 mb-4 ml-11">
                  {section.description}
                </p>
              )}
              <div className="space-y-2">
                {section.endpoints.map((endpoint, i) => (
                  <EndpointCard key={i} endpoint={endpoint} />
                ))}
              </div>
            </div>
          ))}

          {/* Auth Flow */}
          <div
            id="auth-flow"
            ref={el => { sectionRefs.current['auth-flow'] = el; }}
            className="scroll-mt-24"
          >
            <div className="flex items-center gap-3 mb-4">
              <div className="w-8 h-8 rounded-lg bg-brand/10 flex items-center justify-center">
                <i className="fas fa-route text-brand text-sm" />
              </div>
              <h2 className="text-xl font-bold text-gray-900 dark:text-white">
                Autentifikačný flow
              </h2>
            </div>
            <div className="bg-white dark:bg-slate-900 shadow-sm border border-gray-200 dark:border-gray-700/50 rounded-lg p-4">
              <CodeBlock code={AUTH_FLOW} />
            </div>
          </div>

          {/* Error Codes */}
          <div
            id="errors"
            ref={el => { sectionRefs.current['errors'] = el; }}
            className="scroll-mt-24"
          >
            <div className="flex items-center gap-3 mb-4">
              <div className="w-8 h-8 rounded-lg bg-brand/10 flex items-center justify-center">
                <i className="fas fa-exclamation-triangle text-brand text-sm" />
              </div>
              <h2 className="text-xl font-bold text-gray-900 dark:text-white">
                Chybové stavy
              </h2>
            </div>
            <div className="bg-white dark:bg-slate-900 shadow-sm border border-gray-200 dark:border-gray-700/50 rounded-lg overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-gray-50 dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700">
                    <th className="text-left px-4 py-2.5 font-medium text-gray-500 dark:text-gray-400">Kód</th>
                    <th className="text-left px-4 py-2.5 font-medium text-gray-500 dark:text-gray-400">Význam</th>
                  </tr>
                </thead>
                <tbody>
                  {ERROR_CODES.map(({ code, meaning }) => (
                    <tr key={code} className="border-b border-gray-100 dark:border-gray-800 last:border-0">
                      <td className="px-4 py-2.5">
                        <code className={`font-mono font-bold ${
                          code < 300 ? 'text-emerald-600 dark:text-emerald-400' :
                          code < 500 ? 'text-amber-600 dark:text-amber-400' :
                          'text-red-600 dark:text-red-400'
                        }`}>{code}</code>
                      </td>
                      <td className="px-4 py-2.5 text-gray-700 dark:text-gray-300">{meaning}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
