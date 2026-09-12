# API referencia

Kompletná referencia REST API endpointov pre frontend integráciu.

**Base URL:** `/api` (relatívna cesta, proxy cez Vite dev server alebo Docker nginx)

**Autentifikácia:** JWT Bearer token v `Authorization` headeri. Token sa ukladá do `localStorage('token')`.

**HTTP klient:** `frontend/lib/apiClient.ts` — wrapper okolo `fetch()` s automatickým JWT injektovaním, 401 handlingom a slovenskou lokalizáciou chýb.

---

## 1. Autentifikácia (`/api/auth/`)

### `POST /api/auth/register/`

Registrácia nového používateľa.

**Request:**
```json
{
  "email": "user@example.com",
  "username": "novak",
  "password": "securePassword123",
  "first_name": "Ján",
  "last_name": "Novák"
}
```

**Response `201`:**
```json
{ "success": true }
```

---

### `POST /api/auth/token/`

Vydanie JWT access + refresh tokenu (SimpleJWT `TokenObtainPairView`).

**Request:**
```json
{
  "email": "user@example.com",
  "password": "securePassword123"
}
```

**Response `200`:**
```json
{
  "access": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
}
```

---

### `POST /api/auth/token/refresh/`

Obnovenie expirovaného access tokenu.

**Request:**
```json
{ "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..." }
```

**Response `200`:**
```json
{ "access": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..." }
```

---

### `GET /api/auth/profile/`

Profil aktuálne prihláseného používateľa. Vyžaduje JWT.

**Response `200`:**
```json
{
  "id": "1",
  "email": "user@example.com",
  "username": "novak",
  "first_name": "Ján",
  "last_name": "Novák",
  "subscription_plan": "plus",
  "is_staff": false,
  "is_superuser": false
}
```

**Frontend typ:** `User` (`frontend/types.ts`)

---

### `PATCH /api/auth/profile/`

Úprava profilu. Vyžaduje JWT. Posiela len zmenené polia.

**Request:**
```json
{
  "first_name": "Ján",
  "last_name": "Novák"
}
```

**Response `200`:** Rovnaký tvar ako `GET /api/auth/profile/`.

---

### `POST /api/auth/change-password/`

Zmena hesla. Vyžaduje JWT.

**Request:**
```json
{
  "old_password": "staréHeslo",
  "new_password": "novéHeslo123"
}
```

**Response `200`:**
```json
{ "success": true }
```

---

## 2. Firmy (`/api/companies/`)

### `GET /api/companies/search/?q=<query>`

Fulltextové vyhľadávanie podľa IČO alebo názvu firmy.

**Query parametre:**
| Param | Typ | Popis |
|---|---|---|
| `q` | string | Hľadaný výraz (IČO alebo prefix názvu) |

**Response `200`:**
```json
{
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
}
```

**Frontend typ:** `Company` (po mapovaní cez `mapCompanyResponse`)

---

### `GET /api/companies/<ico>/`

Detail firmy podľa IČO. Obsahuje finančné dáta, exekutívu, ORSR profil, dlhy, DPH status.

**Response `200`:** Plná odpoveď backendu, mapovaná na frontend typ `Company`.

**Kľúčové polia v odpovedi:**

| Pole | Typ | Popis |
|---|---|---|
| `ico` | string | IČO firmy (8 číslic) |
| `nazov_UJ` | string | Obchodné meno |
| `legal_form` | string | Právna forma (text) |
| `datum_zalozenia` | string\|null | Dátum založenia (ISO) |
| `datum_zrusenia` | string\|null | Dátum zrušenia (ISO), `null` = aktívna |
| `mesto`, `ulica`, `psc` | string | Adresa sídla |
| `debt_vszp` | number | Dlh na VšZP (EUR) |
| `debt_soc_poist` | number | Dlh na Sociálnej poisťovni (EUR) |
| `tax_debt` | number | Daňový nedoplatok (EUR) |
| `last_insurance_debt` | string | Dátum poslednej kontroly dlhov |
| `ic_dph` | string\|null | IČ DPH |
| `vat_payer` | boolean | Je platca DPH |
| `tax_reliability` | string | Spoľahlivosť daňového subjektu |
| `fs_update_date` | string | Dátum aktualizácie údajov z FS |
| `financials` | array | Finančné výsledky po rokoch |
| `executives` | array | Štatutárne orgány |
| `connections` | array | Prepojenia cez osoby |
| `orsr_profile` | object\|null | Profil z Obchodného registra |

**`financials[]` položka:**

| Pole | Typ |
|---|---|
| `year` | number |
| `revenue` | number |
| `profit` | number |
| `profitAfterTax` | number\|null |
| `totalRevenue` | number |
| `costs` | number |
| `incomeTax` | number |
| `assetsTotal` | number |
| `assetsTangible` | number |
| `assetsIntangible` | number |
| `assetsFinancial` | number |
| `assetsInventory` | number |
| `assetsReceivablesLong` | number |
| `assetsReceivablesShort` | number |
| `assetsFinancialAccounts` | number |
| `equity` | number |
| `equityBasic` | number |
| `equityCapitalFunds` | number |
| `equityProfitFunds` | number |
| `equityRetained` | number |
| `liabilitiesTotal` | number |
| `liabilitiesReserves` | number |
| `liabilitiesLong` | number |
| `liabilitiesShort` | number |
| `liabilitiesAccruals` | number |
| `debtRatio` | number\|null |
| `grossMargin` | number\|null |

`profit` je **výsledok hospodárenia z hospodárskej činnosti** (pred zdanením);
`profitAfterTax` je výsledok za účtovné obdobie po zdanení. Bývalý jediný riadok
`profit` niesol podľa okolností jeden alebo druhý, preto sa obe veličiny už
nespájajú. `profitAfterTax` je `null` pre každý záznam, ktorý nebol znovu
načítaný od rozdelenia (2026-09-12) — `null` tu znamená „riadok nebol prečítaný“,
nie nulu.

**`orsr_profile.structured` objekt:**

| Pole | Typ | Popis |
|---|---|---|
| `statutarny_organ` | OrsrPerson[] | Konatelia / štatutári |
| `statutarny_organ_typ` | string | "konateľ" / "predstavenstvo" |
| `spolocnici` | OrsrPerson[] | Spoločníci (s.r.o.) |
| `vklady_spolocnikov` | OrsrContribution[] | Vklady spoločníkov |
| `prokura` | OrsrPerson[] | Prokuristi |
| `predstavenstvo` | OrsrPerson[] | Členovia predstavenstva (a.s., družstvo) |
| `dozorna_rada` | OrsrPerson[] | Dozorná rada (a.s.) |
| `kontrolna_komisia` | OrsrPerson[] | Kontrolná komisia (družstvo) |
| `akcionari` | OrsrPerson[] | Akcionári (a.s.) |
| `akcie` | OrsrPredmet[] | Emitované akcie (a.s.) |
| `predmet_podnikania` | OrsrPredmet[] | Predmety podnikania |
| `dalsie_pravne_skutocnosti` | OrsrPredmet[] | Ďalšie právne skutočnosti |
| `vyska_zakladneho_imania` | OrsrCapital | Základné imanie + splatenie |
| `konanie` | string | Spôsob konania menom spoločnosti |

---

### `GET /api/companies/<ico>/report/`

Celý firemný report ako PDF (`application/pdf`), vykreslený na serveri cez
WeasyPrint zo šablóny `backend/companies/templates/company_report.html`.
Nevyžaduje JWT.

**Response `200`:** binárne PDF, `Content-Disposition: attachment;
filename="<ico>_<názov>.pdf"`.

**Response `404`:** `{"detail": "Firma s týmto IČO nebola nájdená."}`

**Response `500`:** `{"detail": "Report sa nepodarilo vygenerovať. Skúste to
prosím znova."}` — obstarané tak, aby odpoveď pre anonymného volajúceho
neobsahovala text podkladovej výnimky (cesta k modulu, stopa WeasyPrintu).

Report obsahuje to, čo klientský export v prehliadači nemá: rizikové skóre,
evidované nedoplatky, tabuľku ukazovateľov s uvedeným základom rentability,
Altmanov a Tafflerov model, prehľad hospodárskych výsledkov, štatutárov a
sektorové porovnanie. Naopak **neobsahuje graf prepojení** — ten kreslí
`frontend/utils/pdfExport.ts`, ktorý si prehliadač skladá sám a používa ho
tlačidlo „Stiahnuť PDF“ na stránke firmy. Dve cesty k reportu sa teda
neprekrývajú v obsahu, ale ani jedna nie je nadmnožinou tej druhej; zlúčenie
je otvorené rozhodnutie, nie hotová vec.

**Frontend volajúci:** žiadny. Endpoint je dnes verejné API pre tretie strany,
nie to, čo obsluhuje tlačidlo v aplikácii — pozri `docs/SOURCE_DATA_INTEGRITY.md`.

**Spotreba:** vykreslenie je CPU-náročné a endpoint je `AllowAny`, preto je
naň nasadený throttle (pozri `REPORT_THROTTLE_RATE` v `companies/views.py`).

---

## 3. Graf prepojení (`/api/companies/<ico>/graph/`)

### `GET /api/companies/<ico>/graph/`

Graf osôb a firiem prepojených cez spoločné osoby. Nevyžaduje JWT.

**Response `200`:**
```json
{
  "nodes": [
    { "id": "company_31560636", "type": "company", "label": "TMR, a.s.", "ico": "31560636", "status": "Aktívna" },
    { "id": "person_123", "type": "person", "label": "Ing. Ján Novák", "rolesCount": 3 }
  ],
  "edges": [
    { "source": "person_123", "target": "company_31560636", "role": "Konateľ", "isActive": true }
  ],
  "meta": {
    "center_node": "company_31560636",
    "depth": 2,
    "total_nodes": 11,
    "truncated": false
  }
}
```

**Frontend typ:** `GraphApiResponse` (`frontend/components/graph/graphTypes.ts`)

**Role na hranách:** `Konateľ`, `Spoločník`, `Prokurista`, `Predstavenstvo`, `Dozorná rada`, `Akcionár`

---

### `GET /api/persons/<id>/graph/`

Graf prepojení z pohľadu konkrétnej osoby. Rovnaký response formát ako company graph.

---

### `GET /api/persons/<id>/`

Detail osoby.

---

## 4. Watchlist (`/api/watchlist/`)

Vyžaduje JWT.

### `GET /api/watchlist/`

Zoznam sledovaných firiem.

**Response `200`:**
```json
[
  {
    "id": "w1",
    "ico": "50059959",
    "name": "Quantum Solutions s. r. o.",
    "status": "Aktívna",
    "riskScore": 68,
    "addedAt": "2024-01-15"
  }
]
```

**Frontend typ:** `WatchlistEntry[]`

---

### `POST /api/watchlist/`

Pridanie firmy do watchlistu.

**Request:**
```json
{ "ico": "31560636" }
```

**Response `201`:**
```json
{ "success": true }
```

---

### `DELETE /api/watchlist/<id>/`

Odstránenie z watchlistu.

**Response `204`:** Prázdna odpoveď.

---

## 5. Štatistiky

### `GET /api/stats/landing/`

Štatistiky pre landing page. Nevyžaduje JWT.

**Response `200`:**
```json
{
  "companiesIndexed": 1250000,
  "dailyChecks": 45000,
  "riskyCompaniesDetected": 120
}
```

---

## 6. Registre — trigger endpointy (`/api/registers/`)

Tieto endpointy spúšťajú asynchrónne Celery tasky. Používané z admin panelu.

| Endpoint | Popis |
|---|---|
| `GET /api/registers/trigger-ruz-fetch/` | Spustí inkrementálny RUZ fetch |
| `GET /api/registers/trigger-insurance-debt-check/` | Kontrola poistných dlhov |
| `GET /api/registers/trigger-fs-update/` | Aktualizácia dát z Finančnej správy |

---

## 7. Admin API (`/api/admin/`)

Prístup obmedzený na `is_staff` používateľov. Vyžaduje JWT.

### Dashboard

| Endpoint | Metóda | Popis |
|---|---|---|
| `/api/admin/metrics/overview/` | GET | Prehľad (firmy, sync, users) |
| `/api/admin/metrics/sync/` | GET | Sync zdroje a throughput |
| `/api/admin/metrics/business/` | GET | Business metriky |
| `/api/admin/metrics/system/` | GET | Systémové info (DB, Redis, Celery) |

### Firmy

| Endpoint | Metóda | Popis |
|---|---|---|
| `/api/admin/companies/` | GET | Zoznam firiem (paginovaný) |
| `/api/admin/companies/presets/` | GET | Dostupné preset filtre |
| `/api/admin/companies/report/` | GET | Súhrn nad filtrovaným querysetom |
| `/api/admin/companies/report/?export=csv` | GET | Export reportu do CSV |
| `/api/admin/companies/report/?export=xlsx` | GET | Export reportu do XLSX |
| `/api/admin/company-filters/` | GET/POST | Uložené filtre používateľa |
| `/api/admin/company-filters/<id>/` | PATCH/DELETE | Úprava alebo zmazanie filtra |

**Query parametre:** Štandardné DRF filtrovanie a pagination + `preset`, `filter_builder`, `saved_filter`.

**Report režimy:**

- `mode=light` (**default**): rýchly report bez ťažkých agregácií; vracia základné počty a ostatné sumy/priemery sú `0`.
- `mode=full`: plný report vrátane súm (`revenue_sum`, `profit_sum`, debt sums), priemerov a `top_companies`.

Svetlý režim je predvolený zámerne — `_is_light_mode`
(`adminapi/views/companies.py`) vráti `True` pre všetko okrem `mode=full`, aby
zostal zoznamový endpoint použiteľný nad veľkými dátami. `light=1` je len
ďalší spôsob, ako si vyžiadať to isté; `mode=full` je jediná hodnota, ktorá
agregácie naozaj spustí.

### Používatelia

| Endpoint | Metóda | Popis |
|---|---|---|
| `/api/admin/users/` | GET | Zoznam používateľov |
| `/api/admin/users/<id>/` | PATCH | Úprava používateľa |
| `/api/admin/users/<id>/impersonate/` | POST | Impersonácia (superuser only) |

### Sync Jobs

| Endpoint | Metóda | Popis |
|---|---|---|
| `/api/admin/sync/jobs/` | GET | Zoznam sync jobov |
| `/api/admin/sync/jobs/` | POST | Spustenie nového sync jobu |
| `/api/admin/sync/jobs/<id>/pause/` | POST | Pozastavenie jobu |
| `/api/admin/sync/jobs/<id>/resume/` | POST | Obnovenie jobu |
| `/api/admin/sync/jobs/<id>/cancel/` | POST | Zrušenie jobu |
| `/api/admin/sync/jobs/<id>/retry-failed/` | POST | Opakovanie zlyhaných položiek |

**POST `/api/admin/sync/jobs/` request:**
```json
{
  "job_type": "ruz_full",
  "parameters": {},
  "notes": "Manual trigger"
}
```

### Company Sync Status

| Endpoint | Metóda | Popis |
|---|---|---|
| `/api/admin/sync/companies/` | GET | Sync stav per firma |

### Fronty a plánované tasky

| Endpoint | Metóda | Popis |
|---|---|---|
| `/api/admin/sync/queues/` | GET | Hĺbka Celery frontov |
| `/api/admin/sync/scheduled/` | GET | Zoznam plánovaných taskov |
| `/api/admin/sync/scheduled/<id>/toggle/` | POST | Zapnutie/vypnutie tasku |

### Focus Mode

| Endpoint | Metóda | Popis |
|---|---|---|
| `/api/admin/sync/focus-mode/` | GET | Aktuálny stav focus mode |
| `/api/admin/sync/focus-mode/enter/` | POST | Vstup do focus mode |
| `/api/admin/sync/focus-mode/exit/` | POST | Výstup z focus mode |

### Audit Log

| Endpoint | Metóda | Popis |
|---|---|---|
| `/api/admin/audit/` | GET | Zoznam audit logov (paginovaný) |

### System

| Endpoint | Metóda | Popis |
|---|---|---|
| `/api/admin/system/health/` | GET | Health check (DB, Redis, workers) |
| `/api/admin/system/info/` | GET | Systémové informácie |

---

## 8. Zdravie

### `GET /healthz/`

Liveness endpoint. Nevyžaduje autentifikáciu.

**Response `200`:**
```json
{ "status": "ok" }
```

---

## 9. Frontend typy

Všetky TypeScript typy sú definované v:
- `frontend/types.ts` — hlavné doménové typy (`Company`, `User`, `Financials`, `OrsrProfile`, ...)
- `frontend/components/graph/graphTypes.ts` — graf typy (`GraphNode`, `GraphEdge`, `GraphApiResponse`)
- `frontend/admin/types.ts` — admin typy (`SyncJob`, `AdminCompany`, `AuditLogEntry`, ...)

## 10. Chybové stavy

| Kód | Význam | Frontend handling |
|---|---|---|
| `200` | Úspešné čítanie | — |
| `201` | Úspešné vytvorenie | — |
| `204` | Úspešné vymazanie (bez body) | `apiClient` vráti `{}` |
| `400` | Validačná chyba | Lokalizované chybové hlášky |
| `401` | Neplatný/expirovaný token | Automatický logout + `auth:unauthorized` event |
| `403` | CSRF / Forbidden | Detekcia CSRF vs origin problémov |
| `404` | Nenájdené | — |
| `500` | Interná chyba servera | — |

## 11. Autentifikačný flow

```
1. POST /api/auth/token/ → access + refresh token
2. localStorage.setItem('token', access)
3. Každý request: Authorization: Bearer <access>
4. Pri 401: localStorage.removeItem('token') + CustomEvent('auth:unauthorized')
5. AuthContext počúva event → logout()
```

## 12. Konfigurácia

| Premenná | Súbor | Default | Popis |
|---|---|---|---|
| `API_BASE_URL` | `frontend/constants.ts` | `/api` | Base URL pre API volania |
| `ENABLE_MOCK_DATA` | `frontend/constants.ts` | `false` | Mock dáta pre vývoj bez backendu |

