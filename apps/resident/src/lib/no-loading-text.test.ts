import { describe, expect, it } from 'vitest';
import { STRINGS } from './i18n';

// Every resident source file except tests, as text.
const sources = import.meta.glob(['../**/*.{ts,tsx}', '!../**/*.test.{ts,tsx}'], { query: '?raw', import: 'default', eager: true }) as Record<string, string>;

describe('no plain "Loading…" left in the resident app', () => {
  it('has no generic loading string in either language', () => {
    for (const lang of ['en', 'ms'] as const) {
      const values = Object.values(STRINGS[lang]) as string[];
      expect(values).not.toContain('Loading…');
      expect(values).not.toContain('Memuatkan…');
      expect(Object.keys(STRINGS[lang])).not.toContain('loading');
    }
  });

  it("does not use t(lang, 'loading') anywhere", () => {
    expect(Object.keys(sources).length).toBeGreaterThan(20);
    for (const [file, text] of Object.entries(sources)) expect(text, file).not.toMatch(/t\(lang, 'loading'\)|>Loading…</);
  });
});
