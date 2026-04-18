# API referencia

Aktualna referencia endpointov definovanych v Django URL konfiguracii.

Base URL (lokal): `http://localhost:8080`

## 1. Health

### `GET /healthz/`

Rychly liveness endpoint backendu.

Priklad:

```bash
curl http://localhost:8080/healthz/
```

## 2. Auth (`/api/auth/`)

### `POST /api/auth/register/`

Registracia pouzivatela.

### `POST /api/auth/token/`

Vydanie JWT access/refresh tokenu.

### `POST /api/auth/token/refresh/`

Obnovenie access tokenu.

### `GET /api/auth/profile/`

Vrati profil aktualne autentifikovaneho pouzivatela.

### `PATCH /api/auth/profile/`

Uprava profilu aktualneho pouzivatela.

## 3. Companies (`/api/companies/`)

### `GET /api/companies/`

Zoznam firiem (router list endpoint).

### `GET /api/companies/search/?q=<query>`

Vyhladavanie podla ICO alebo prefixu nazvu firmy.

Priklad:

```bash
curl "http://localhost:8080/api/companies/search/?q=MARO"
```

### `GET /api/companies/<ico>/`

Detail firmy podla ICO.

Priklad:

```bash
curl "http://localhost:8080/api/companies/48173894/"
```

## 4. Registers trigger endpointy (`/api/registers/`)

Tieto endpointy spustaju asynchronne Celery tasky.

### `GET /api/registers/trigger-ruz-fetch/`

Spusti RUZ fetch task.

### `GET /api/registers/trigger-insurance-debt-check/`

Spusti hromadnu kontrolu poistnych dlhov pre firmy.

### `GET /api/registers/trigger-fs-update/`

Spusti aktualizaciu FS dat.

## 5. API mapa

```mermaid
flowchart TD
    A[/healthz/]:::public
    B[/api/auth/register/]:::public
    C[/api/auth/token/]:::public
    D[/api/auth/token/refresh/]:::public
    E[/api/auth/profile/]:::auth
    F[/api/companies/search/]:::public
    G[/api/companies/<ico>/]:::public
    H[/api/registers/trigger-ruz-fetch/]:::public
    I[/api/registers/trigger-insurance-debt-check/]:::public
    J[/api/registers/trigger-fs-update/]:::public

    classDef public fill:#e8f4ff,stroke:#1b76d1,color:#0b3d6e
    classDef auth fill:#fff4e5,stroke:#d97706,color:#7c2d12
```

## 6. Poznamky pre frontend integraciu

- Frontend pouziva `API_BASE_URL = '/api'`, teda vola backend cez relativnu cestu.
- Pri local dev ide komunikacia cez Vite proxy / Docker networking podla prostredia.
- Pri `401` je vo frontend API wrapperi implementovane vycistenie tokenu a forcing re-auth flow.

## 7. Chybove stavy

Typicke HTTP odpovede:

- `200` - uspesne citanie
- `201` - uspesna registracia
- `400` - validacna chyba payloadu
- `401` - neplatny alebo expirovany token
- `404` - firma/endpoint nenajdeny
- `500` - interny backend error

Pri debugovani sa oplati sledovat backend logs (`docker compose logs -f backend`).
