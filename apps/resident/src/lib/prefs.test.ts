import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { loadPrefs } from './prefs';

const KEY = 'floodready.prefs.v1';
const VALID = /^[A-Za-z0-9_-]{16,64}$/;

describe('device id', () => {
  beforeEach(() => localStorage.clear());

  it('is generated with crypto.randomUUID and matches the API pattern', () => {
    const id = loadPrefs().deviceId;
    expect(id).toMatch(VALID);
    expect(loadPrefs().deviceId).not.toBe(id); // nothing saved yet: a fresh one each time
  });

  it('keeps a stored id that matches the pattern', () => {
    localStorage.setItem(KEY, JSON.stringify({ lang: 'en', streets: [], deviceId: 'dev_abc123def456ghi789' }));
    expect(loadPrefs().deviceId).toBe('dev_abc123def456ghi789');
  });

  it.each(['short', 'has space 0123456789', 'x'.repeat(65), 'bad/char/0123456789', ''])('regenerates the invalid id %j', (bad) => {
    localStorage.setItem(KEY, JSON.stringify({ lang: 'ms', streets: ['BBR-a'], deviceId: bad }));
    const p = loadPrefs();
    expect(p.deviceId).toMatch(VALID);
    expect(p.deviceId).not.toBe(bad);
    expect(p.streets).toEqual(['BBR-a']);
  });

  describe('without crypto.randomUUID (insecure context)', () => {
    afterEach(() => vi.unstubAllGlobals());

    it('falls back to crypto.getRandomValues', () => {
      vi.stubGlobal('crypto', { getRandomValues: (a: Uint8Array) => a.fill(171) });
      const id = loadPrefs().deviceId;
      expect(id).toMatch(VALID);
      expect(id).toBe('ab'.repeat(16));
    });

    it('still returns prefs when no crypto is available at all', () => {
      vi.stubGlobal('crypto', undefined);
      expect(loadPrefs().deviceId).toMatch(VALID);
    });

    it('keeps working when randomUUID throws', () => {
      vi.stubGlobal('crypto', { randomUUID: () => { throw new Error('insecure'); }, getRandomValues: (a: Uint8Array) => a.fill(1) });
      expect(loadPrefs().deviceId).toMatch(VALID);
    });
  });
});

describe('language on a first visit', () => {
  beforeEach(() => localStorage.clear());
  afterEach(() => vi.unstubAllGlobals());

  it("starts in Malay when the phone's language is Malay, otherwise English", () => {
    vi.stubGlobal('navigator', { ...navigator, language: 'ms-MY' });
    expect(loadPrefs().lang).toBe('ms');
    vi.stubGlobal('navigator', { ...navigator, language: 'en-GB' });
    expect(loadPrefs().lang).toBe('en');
  });

  it('keeps a saved choice over the phone language', () => {
    vi.stubGlobal('navigator', { ...navigator, language: 'ms-MY' });
    localStorage.setItem(KEY, JSON.stringify({ lang: 'en', streets: [], deviceId: 'dev_abc123def456ghi789' }));
    expect(loadPrefs().lang).toBe('en');
  });
});
