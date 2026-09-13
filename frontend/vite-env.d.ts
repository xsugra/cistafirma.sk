/// <reference types="vite/client" />

/**
 * The two Google Maps values that come from the Google Cloud console rather than
 * from the repository.
 *
 * Both reach the bundle through Vite's `import.meta.env`, which means Vite
 * **inlines them into the built JavaScript**. That is fine and expected for a
 * Maps JavaScript API key -- it is a public browser credential by design, and
 * what protects it is the HTTP-referrer and API restriction set on it in the
 * console, never secrecy. It is not fine for anything else, so do not give a
 * `VITE_` name to a value that has to stay private: the prefix is exactly what
 * publishes it to every visitor.
 *
 * Declared so that `tsc --noEmit` (`npm run typecheck`, run by the
 * `frontend_tests` CI job) rejects a misspelt name, instead of the app silently
 * reading `undefined` and showing the "no key configured" card in production
 * while the key sits right there in `.env`.
 *
 * The declarations below would not achieve that on their own. `vite/client` gives
 * `ImportMetaEnv` a `[key: string]: any` fallback, so every undeclared name
 * typechecks as `any` and a typo compiles clean. Declaring `ViteTypeOptions` with
 * `strictImportMetaEnv` is what removes the fallback -- and then the two names
 * below really are the only `VITE_*` keys this app may read.
 */
interface ViteTypeOptions {
    strictImportMetaEnv: unknown;
}

interface ImportMetaEnv {
    /** Google Cloud -> APIs & Services -> Credentials. Absent means no map. */
    readonly VITE_GOOGLE_MAPS_API_KEY?: string;
    /** Required for advanced markers and for the dark map style. */
    readonly VITE_GOOGLE_MAPS_MAP_ID?: string;
}
