import react from '@vitejs/plugin-react';
import { defineConfig } from 'vitest/config';

// Tests run without the PWA plugin (no service worker in jsdom).
export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test-setup.ts'],
    // Stylesheets are stubbed out, except the app's own, which the loader test reads as text (?raw).
    css: { include: [/src\/styles\.css/] },
  },
});
