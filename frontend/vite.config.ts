import path from 'path';
import {defineConfig, loadEnv} from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({mode}) => {
    const env = loadEnv(mode, '.', '');
    return {
        plugins: [react()],
        define: {
            'process.env.API_KEY': JSON.stringify(env.GEMINI_API_KEY),
            'process.env.GEMINI_API_KEY': JSON.stringify(env.GEMINI_API_KEY)
        },
        resolve: {
            alias: {
                '@': path.resolve(__dirname, '.'),
            }
        },
        base: '/static/',
        build: {
            // Priečinok, kam sa uloží build
            outDir: 'dist',
            // Vyčistiť priečinok pred každým buildom
            emptyOutDir: true,
            manifest: true, // Užitočné pre pokročilejšie Django integrácie (voliteľné)
        },
        server: {
            // Toto je len pre vývoj (npm run dev), aby si nemusel riešiť CORS
            proxy: {
                '/api': {
                    target: 'http://localhost:8000',
                    changeOrigin: true,
                }
            }
        },
    }
});
