import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
export default defineConfig({
    plugins: [react()],
    build: {
        outDir: 'dist',
    },
    server: {
        proxy: {
            '/api': {
                target: 'http://0.0.0.0:8000',
                changeOrigin: true,
            },
        },
    },
});
