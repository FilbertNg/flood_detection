import react from '@vitejs/plugin-react';
import { defineConfig } from 'vitest/config';

// Tests run without the PWA plugin (no service worker in jsdom).
export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test-setup.ts'],
    css: false,
  },
});
