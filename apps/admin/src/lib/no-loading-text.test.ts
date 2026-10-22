import { describe, expect, it } from 'vitest';

// Every admin source file except tests, as text.
const sources = import.meta.glob(['../**/*.{ts,tsx}', '!../**/*.test.{ts,tsx}'], { query: '?raw', import: 'default', eager: true }) as Record<string, string>;

describe('no plain "Loading…" left in the admin app', () => {
  it('says what is loading, next to the logo-fill loader', () => {
    expect(Object.keys(sources).length).toBeGreaterThan(15);
    for (const [file, text] of Object.entries(sources)) expect(text, file).not.toMatch(/Loading…|Loading \{gid\}…/);
  });
});
