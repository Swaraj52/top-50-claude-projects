/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

const API = process.env.VITE_API_URL ?? 'http://127.0.0.1:8001';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5101,
    strictPort: true,
    proxy: { '/api': { target: API, changeOrigin: false } },
  },
  preview: { port: 5101 },
  build: { outDir: 'dist', sourcemap: true },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    css: false,
  },
});
