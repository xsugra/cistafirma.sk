/// <reference types="vitest/config" />
import path from 'path';
import {defineConfig, loadEnv} from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig(({mode}) => {
    // Load root .env file (local dev) and merge process env (Docker runtime).
    const env = {
        ...process.env,
        ...loadEnv(mode, '../', ''),
    };

    // There is no build-time map check any more, and that is not a loss of
    // vigilance. The map used to need a Google key, so a build without one shipped
    // a bundle in which every seat map announced the missing key while exiting 0 --
    // and this was the only place that saw both the build and its environment, so
    // it was where that silence was broken. MapLibre and OpenStreetMap want no key,
    // so there is nothing to be missing, and a check here could only ever warn
    // about a variable that no longer exists.

    // Backend configuration from root .env
    const BACKEND_HOST = env.BACKEND_HOST || 'localhost';
    const BACKEND_PORT = env.BACKEND_PORT || '8080';
    const backendUrl = `http://${BACKEND_HOST}:${BACKEND_PORT}`;

    // Frontend configuration from root .env
    const FRONTEND_PORT = env.FRONTEND_PORT || '5173';

    // Extra names this dev server answers to, beyond the loopback ones.
    //
    // Vite refuses any request whose `Host` it does not recognise, answering
    // "Blocked request. This host is not allowed." It knows `localhost` and bare
    // IP addresses, and a name that resolves here from somewhere else -- a
    // Tailscale name, a LAN name -- is neither. So the refusal lands before the
    // proxy below is ever reached, and it reads as the app being down rather
    // than as a gap in this file.
    //
    // A leading dot matches the host and every subdomain of it, which is the
    // form to use for a name that may change. Loopback is re-added at the point
    // of use, because assigning `allowedHosts` replaces Vite's defaults instead
    // of extending them.
    const EXTRA_ALLOWED_HOSTS = (env.FRONTEND_ALLOWED_HOSTS || '')
        .split(',')
        .map((host) => host.trim())
        .filter(Boolean);

    return {
        plugins: [react(), tailwindcss()],
        resolve: {
            alias: {
                '@': path.resolve(__dirname, '.'),
            }
        },
        base: '/',
        // Vite fills `import.meta.env` from `envDir`, which is resolved against
        // this config's root and defaults to it -- so out of the box Vite reads
        // `frontend/.env`, while the `loadEnv(mode, '../', '')` above fills only
        // *this file's* local variables (BACKEND_HOST, FRONTEND_PORT) and never
        // reaches the app. Pointing `envDir` at the repo root is what makes the
        // root `.env` -- this project's single source of truth -- the file the
        // app reads too.
        //
        // In a container the same path resolves to `/`, because `frontend/` is
        // mounted (or built) at `/app` and its parent is the container root.
        // There the value arrives by the other route `loadEnv` merges: it folds
        // in every `VITE_`-prefixed name already in `process.env`, which is how
        // compose's `env_file: ./.env` reaches the dev server. `frontend/.env` is
        // consequently read by nobody; `frontend/env.default` stays as a template
        // for a file that is no longer read.
        //
        // Either way the prefix is the whole boundary: only `VITE_` names are
        // exposed, so a root-`.env` value without it cannot reach the bundle.
        // That matters more here than it looks -- see `vite-env.d.ts`, where the
        // set of `VITE_` names this app may read is now empty and a stray one is a
        // compile error rather than a silently published secret.
        envDir: '../',
        build: {
            // Priečinok, kam sa uloží build
            outDir: 'dist',
            // Vyčistiť priečinok pred každým buildom
            emptyOutDir: true,
            manifest: true, // Užitočné pre pokročilejšie Django integrácie (voliteľné)
        },
        server: {
            // Dev server port from root .env
            port: parseInt(FRONTEND_PORT),
            // Left unset when nothing extra is configured, so Vite's own
            // defaults keep charge of a plain local browser.
            ...(EXTRA_ALLOWED_HOSTS.length
                ? {allowedHosts: ['localhost', '127.0.0.1', ...EXTRA_ALLOWED_HOSTS]}
                : {}),
            // Proxy API requests to backend (configured from root .env)
            // This allows frontend to make requests to /api which get proxied to backend
            proxy: {
                '/api/': {
                    target: backendUrl,
                    changeOrigin: true,
                    // Forward the caller's address as `X-Forwarded-For`, the
                    // way `nginx.conf.template` does in the built image. Without it the
                    // backend sees every request coming from this dev server,
                    // so anything keyed by client address -- DRF's throttling,
                    // the /metrics private-address check -- treats the whole
                    // internet as one caller.
                    xfwd: true,
                }
            }
        },
        test: {
            environment: 'jsdom',
            globals: false,
            setupFiles: ['./test/setup.ts'],
        },
    }
});
