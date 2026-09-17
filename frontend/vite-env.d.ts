/// <reference types="vite/client" />

/**
 * This app reads no `VITE_*` variable at all, and that is now the guarantee.
 *
 * Vite **inlines** every `import.meta.env.VITE_*` name into the built JavaScript,
 * which makes the prefix a publication mechanism rather than a namespace: a
 * `VITE_` name is readable by every visitor, so never give one to a value that has
 * to stay private. Declaring the set here is what makes that enforceable --
 * `vite/client` gives `ImportMetaEnv` a `[key: string]: any` fallback, so without
 * `strictImportMetaEnv` below, every undeclared name typechecks as `any`, a typo
 * compiles clean, and the app reads `undefined` in production while the value sits
 * right there in `.env`.
 *
 * The map used to be the exception: it needed `VITE_GOOGLE_MAPS_API_KEY` and
 * `VITE_GOOGLE_MAPS_MAP_ID` from the Google Cloud console. It now draws
 * OpenStreetMap tiles through MapLibre, which wants no key, no account and no
 * card, so those two declarations are gone -- and with nothing left to declare,
 * the empty interface is not an oversight. It says that **any** `VITE_*` read is
 * a mistake, and `tsc --noEmit` (`npm run typecheck`, run by the
 * `frontend_validate` CI job) fails the build over one instead of shipping it.
 *
 * `BASE_URL`, `MODE`, `DEV`, `PROD` and `SSR` still come from `vite/client` and
 * still typecheck; only arbitrary names are refused. Non-`VITE_` values from the
 * root `.env` do reach the frontend container (see `vite.config.ts`), but they
 * reach it as server-side environment variables, not as anything this file types.
 */
interface ViteTypeOptions {
    strictImportMetaEnv: unknown;
}

interface ImportMetaEnv {}
