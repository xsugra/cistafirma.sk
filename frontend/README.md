# Frontend (`frontend/`)

React + Vite + TypeScript aplikacia pre `cistafirma`.

## Stack

- React 19
- Vite 6
- TypeScript
- Recharts (grafy)

## Lokalny vyvoj

```bash
cd /Users/samuelsugra/Code/cistafirma/frontend
npm install
npm run dev
```

Frontend defaultne bezi na:

- `http://localhost:5173/`

## Build

```bash
cd /Users/samuelsugra/Code/cistafirma/frontend
npm run build
npm run preview
```

## Integracia s backendom

- API volania idu cez `API_BASE_URL` v `constants.js`
- default je relativna cesta `/api`
- v lokalnom compose prostredi backend pocuva na hoste `http://localhost:8080`

## Klucove subory

- `api.js` - API wrapper, auth handling, parsing chyb
- `constants.js` - feature flagy a API base konfiguracia
- `App.tsx` - root aplikacie
- `components/` - UI komponenty
- `pages/` - page-level obrazovky

## Poznamka k mock modu

`ENABLE_MOCK_DATA` v `constants.js` vie prepnut frontend do mock rezimu bez backendu.

## Kvalita pred commitom

```bash
cd /Users/samuelsugra/Code/cistafirma/frontend
npm run build
```

Ak build prejde, zakladna integrita frontend kodu je overena.
