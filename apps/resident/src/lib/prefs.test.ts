import { beforeEach, describe, expect, it } from 'vitest';
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
});
