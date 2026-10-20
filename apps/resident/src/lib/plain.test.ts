import { describe, expect, it } from 'vitest';
import { bigWord, headline, keyPoints, rainStrength, riverStatus, weatherPhrase } from './plain';
import type { WeatherHour } from './weather';

const T = (hm: string) => `2024-11-12T${hm}:00+08:00`;
const th = { alert: 3.8, warning: 4.0, danger: 4.2 };
const hours = (chances: (number | null)[], start = 18): WeatherHour[] =>
  chances.map((c, i) => ({ hour: `2026-10-20T${String(start + i).padStart(2, '0')}`, code: 61, isDay: true, rainChance: c }));

describe('bigWord', () => {
  it.each([
    ['normal', 'en', 'Safe'], ['watch', 'en', 'Be alert'], ['warning', 'en', 'Get ready'], ['danger', 'en', 'Move now'],
    ['normal', 'ms', 'Selamat'], ['watch', 'ms', 'Berwaspada'], ['warning', 'ms', 'Bersedia'], ['danger', 'ms', 'Pindah sekarang'],
  ] as const)('%s in %s is "%s"', (level, lang, word) => {
    expect(bigWord(level, lang)).toBe(word);
  });
});

describe('headline', () => {
  it('promises nothing beyond "no warning right now" at Normal', () => {
    expect(headline('normal', null, 'en')).toBe('No flood warning for this street right now.');
  });
  it('gives the expected start time at Warning when there is a window', () => {
    expect(headline('warning', { start: T('21:00'), end: T('23:00') }, 'en')).toBe('Flooding is expected on this street from about 21:00.');
    expect(headline('warning', { start: T('21:00'), end: T('23:00') }, 'ms')).toBe('Banjir dijangka di jalan ini dari kira-kira 21:00.');
  });
  it('says flooding is likely soon at Warning without a window', () => {
    expect(headline('warning', null, 'en')).toBe('Flooding is likely on this street soon.');
  });
  it('says the street may be flooding at Danger, not that it is', () => {
    expect(headline('danger', null, 'en')).toBe('This street may be flooding now. Leave if water is entering your home.');
  });
});

describe('rainStrength', () => {
  it.each([[0, 'none'], [0.4, 'light'], [2.5, 'moderate'], [9.9, 'moderate'], [10, 'heavy']] as const)('%s mm → %s', (mm, s) => {
    expect(rainStrength(mm)).toBe(s);
  });
});

describe('riverStatus', () => {
  it.each([[3.0, 'low'], [3.5, 'near'], [3.8, 'alert'], [4.05, 'warning'], [4.2, 'danger']] as const)('%s m → %s', (wl, s) => {
    expect(riverStatus(wl, th)).toBe(s);
  });
});

describe('weatherPhrase', () => {
  it('says when rain eases', () => {
    expect(weatherPhrase(hours([62, 45, 30, 10]), '2026-10-20T18:10:00+08:00', 'en')).toBe('easing by 20:00');
  });
  it('says when rain is likely to start', () => {
    expect(weatherPhrase(hours([10, 20, 55, 70]), '2026-10-20T18:00:00+08:00', 'ms')).toBe('hujan mungkin dari 20:00');
  });
  it('says nothing when it stays the same or the data is missing', () => {
    expect(weatherPhrase(hours([10, 12, 8]), '2026-10-20T18:00:00+08:00', 'en')).toBeNull();
    expect(weatherPhrase(hours([null, null]), '2026-10-20T18:00:00+08:00', 'en')).toBeNull();
    expect(weatherPhrase(null, '2026-10-20T18:00:00+08:00', 'en')).toBeNull();
  });
});

describe('keyPoints', () => {
  const base = { lang: 'en' as const, window: null, gauge: null, hours: null, dataTime: '2026-10-20T18:00:00+08:00', river: null };

  it('reads a quiet Normal street', () => {
    expect(keyPoints({ ...base, level: 'normal', river: { wl: 3.0, th } })).toEqual({ rain: 'None now', river: 'Low', flood: 'Not expected' });
  });
  it('adds "easing" when gauge rain is falling but the chance drops', () => {
    const k = keyPoints({ ...base, level: 'normal', gauge: { mm: 0.5, station: 'X' }, hours: hours([62, 30]) });
    expect(k.rain).toBe('Light, easing');
  });
  it('says heavy now and shows the window start at Warning', () => {
    const k = keyPoints({ ...base, level: 'warning', gauge: { mm: 31, station: 'X' }, hours: hours([88, 80]), window: { start: T('21:00'), end: T('22:00') }, river: { wl: 4.1, th } });
    expect(k).toEqual({ rain: 'Heavy now', river: 'Above warning', flood: 'From ~21:00' });
  });
  it('is honest when there is no river reading', () => {
    expect(keyPoints({ ...base, level: 'danger' }).river).toBe('No reading');
    expect(keyPoints({ ...base, level: 'danger' }).flood).toBe('Likely now');
  });
  it('says rain is likely soon when no gauge has rain but the chance is high', () => {
    expect(keyPoints({ ...base, level: 'watch', hours: hours([55]) })).toMatchObject({ rain: 'Likely soon', flood: 'Possible' });
  });
});
