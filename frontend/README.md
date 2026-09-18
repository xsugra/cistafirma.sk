# Frontend (`frontend/`)

React + Vite + TypeScript aplikacia pre `cistafirma`.

## Stack

- React 19
- Vite 6
- TypeScript 5.8
- Tailwind CSS v4
- Recharts (grafy), maplibre-gl (mapy), react-force-graph-2d (graf vazieb)
- Vitest + Testing Library (testy)

## Lokalny vyvoj

```bash
cd /Users/samuelsugra/Code/cistafirma/frontend
npm install
npm run dev
```

Frontend defaultne bezi na:

- `http://localhost:5173/`

> **Pozor pri `npm install`:** Docker dev kontajner je kanonicky instalator
> zavislosti (Node je pinnuty vo `frontend/Dockerfile`, aby bundled npm 10
> zapisal `package-lock.json` v stabilnom formate). Novsi host npm (11.x)
> preformatuje lockfile a necha pracovny strom spinavy — pri zmene zavislosti
> radsej `docker compose exec frontend npm install`.

## Build

```bash
cd /Users/samuelsugra/Code/cistafirma/frontend
npm run build
npm run preview
```

## Integracia s backendom

- API volania idu cez `API_BASE_URL` v `constants.ts`
- default je relativna cesta `/api`
- v lokalnom compose prostredi backend pocuva na hoste `http://localhost:8080`
  (Vite dev server proxuje `/api/` tam)

## Klucove subory

- `api.ts` - API wrapper, auth handling, parsing chyb
- `lib/apiClient.ts` - nizkourovnovy HTTP klient a JWT handling
- `constants.ts` - feature flagy a API base konfiguracia
- `App.tsx` - root aplikacie
- `components/` - UI komponenty
- `pages/` - page-level obrazovky
- `admin/` - staff admin panel (`AdminApp.tsx`, `api.ts`, `pages/`)

Poznamka: **neexistuje `frontend/src/`** — zdrojove subory su priamo pod
`frontend/`.

## Poznamka k mock modu

`ENABLE_MOCK_DATA` v `constants.ts` vie prepnut frontend do mock rezimu bez
backendu (data berie z `mockData.ts`).

## Kvalita pred commitom

CI (`.gitlab-ci.yml`, joby `frontend_tests` a `frontend_validate`) spusta presne
tieto tri prikazy — spusti ich tiez, aby typecheck alebo test nepadol az v
pipeline:

```bash
docker compose exec -T frontend npm test         # vitest run
docker compose exec -T frontend npm run typecheck # tsc --noEmit
docker compose exec -T frontend npm run build     # vite build
```

`npm run build` sam o sebe overi iba zakladnu integritu kodu — otestuje, ze sa
vsetko skompiluje. Testy a typecheck su samostatne.
