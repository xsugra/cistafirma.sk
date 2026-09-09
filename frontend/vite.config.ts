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
