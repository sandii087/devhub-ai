import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5174,
    proxy: {
      '/api': { target: 'http://127.0.0.1:8001', changeOrigin: false },
      '/auth': { target: 'http://127.0.0.1:8001', changeOrigin: false },
      '/health': { target: 'http://127.0.0.1:8001', changeOrigin: false },
    },
  },
  test: { include: ['src/test/**/*.test.{ts,tsx}'], environment: 'jsdom', setupFiles: './src/test/setup.ts', restoreMocks: true },
});
