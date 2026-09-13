/// <reference types="vitest/config" />
import path from 'path';
import {defineConfig, loadEnv} from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig(({command, mode}) => {
    // Load root .env file (local dev) and merge process env (Docker runtime).
    const env = {
        ...process.env,
        ...loadEnv(mode, '../', ''),
    };

    // A build that has no key ships a bundle whose every seat map announces the
    // missing key -- and exits 0, so nothing downstream notices. This is the one
    // place that sees both the build and the environment it was handed, so it is
    // where the silence is broken. Not an error: the app is expected to build and
    // run without a key (CI does exactly that), it just must not do so quietly.
    if (command === 'build') {
        const missing = ['VITE_GOOGLE_MAPS_API_KEY', 'VITE_GOOGLE_MAPS_MAP_ID'].filter(
            (name) => !env[name],
        );
        if (missing.length) {
            console.warn(
                `\n[vite] Google Maps: ${missing.join(' and ')} not set.\n` +
                    '        The bundle will show "no Google Maps key configured" instead\n' +
                    '        of a map on every company profile. For a deployed image the\n' +
                    '        root .env does not reach the build -- pass it as a build arg\n' +
                    '        (frontend/Dockerfile.prod, .gitlab-ci.yml build_frontend_image).\n',
            );
        }
    }

    // Backend configuration from root .env
    const BACKEND_HOST = env.BACKEND_HOST || 'localhost';
    const BACKEND_PORT = env.BACKEND_PORT || '8080';
    const backendUrl = `http://${BACKEND_HOST}:${BACKEND_PORT}`;

    // Frontend configuration from root .env
    const FRONTEND_PORT = env.FRONTEND_PORT || '5173';

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
        // That matters more here than it looks -- see `vite-env.d.ts`, and
        // `frontend/Dockerfile.prod` for how a production build is given the two
        // `VITE_` values it needs (its build context cannot see the root `.env`).
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
            // Proxy API requests to backend (configured from root .env)
            // This allows frontend to make requests to /api which get proxied to backend
            proxy: {
                '/api/': {
                    target: backendUrl,
                    changeOrigin: true,
                    // Forward the caller's address as `X-Forwarded-For`, the
                    // way `nginx.conf` does in the built image. Without it the
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
