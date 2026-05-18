# API referencia

Aktuálna referencia endpointov definovaných v Django URL konfigurácii.

Base URL (lokálne): `http://localhost:8080`

## 1. Health

### `GET /healthz/`

Rýchly liveness endpoint backendu.

Príklad:

```bash
curl http://localhost:8080/healthz/
```

## 2. Auth (`/api/auth/`)

### `POST /api/auth/register/`

Registrácia používateľa.

### `POST /api/auth/token/`

Vydanie JWT access/refresh tokenu.

### `POST /api/auth/token/refresh/`

Obnovenie access tokenu.

### `GET /api/auth/profile/`

Vráti profil aktuálne autentifikovaného používateľa.

### `PATCH /api/auth/profile/`

Úprava profilu aktuálneho používateľa.

## 3. Companies (`/api/companies/`)

### `GET /api/companies/`

Zoznam firiem (router list endpoint).

### `GET /api/companies/search/?q=<query>`

Vyhľadávanie podľa IČO alebo prefixu názvu firmy.

Príklad:

```bash
curl "http://localhost:8080/api/companies/search/?q=MARO"
```

### `GET /api/companies/<ico>/`

Detail firmy podľa IČO.

Príklad:

```bash
curl "http://localhost:8080/api/companies/48173894/"
```

## 4. Registers – trigger endpointy (`/api/registers/`)

Tieto endpointy spúšťajú asynchrónne Celery tasky.

### `GET /api/registers/trigger-ruz-fetch/`

Spustí RUZ fetch task.

### `GET /api/registers/trigger-insurance-debt-check/`

Spustí hromadnú kontrolu poistných dlhov pre firmy.

### `GET /api/registers/trigger-fs-update/`

Spustí aktualizáciu FS dát.

## 5. Admin API (`/api/admin/`)

Admin API endpointy pre internú správu. Prístup je obmedzený na admin používateľov.

## 6. API mapa

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
    K[/api/admin/...]:::auth

    classDef public fill:#e8f4ff,stroke:#1b76d1,color:#0b3d6e
    classDef auth fill:#fff4e5,stroke:#d97706,color:#7c2d12
```

## 7. Poznámky pre frontend integráciu

- Frontend používa `API_BASE_URL = '/api'`, teda volá backend cez relatívnu cestu.
- Pri local dev ide komunikácia cez Vite proxy / Docker networking podľa prostredia.
- Pri `401` je vo frontend API wrapperi implementované vyčistenie tokenu a vynútenie re-auth flow.

## 8. Chybové stavy

Typické HTTP odpovede:

| Kód | Význam |
|---|---|
| `200` | Úspešné čítanie |
| `201` | Úspešná registrácia |
| `400` | Validačná chyba payloadu |
| `401` | Neplatný alebo expirovaný token |
| `404` | Firma/endpoint nenájdený |
| `500` | Interný backend error |

Pri debugovaní sa oplatí sledovať backend logy (`docker compose logs -f backend`).
