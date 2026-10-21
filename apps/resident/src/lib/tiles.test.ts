import { describe, expect, it } from 'vitest';
import {
  clockHands, dropFillTop, heaviestHour, nextHighWater, pillTicks, pillY, proneTone, rainBars, ringDash, ringTone, scallopPath, tideWave,
} from './tiles';

const T = (hm: string, d = '12') => `2024-11-${d}T${hm}:00+08:00`;

describe('dropFillTop', () => {
  it('fills the drop from the bottom: empty at 0, half at 15, full from 30 mm', () => {
    expect(dropFillTop(0)).toBe(92);
    expect(dropFillTop(15)).toBe(50);
    expect(dropFillTop(30)).toBe(8);
    expect(dropFillTop(61.5)).toBe(8);
  });
});

describe('rainBars and heaviestHour', () => {
  const rain = [0, 0, 1.2, 4, 0.5, 0, 0, 0, 0, 0, 0, 0].map((mm, i) => ({ time: T(`${String(10 + i).padStart(2, '0')}:00`), mm }));

  it('draws one bar per hour, wet hours taller and filled, dry hours a short pale stub', () => {
    const bars = rainBars(rain);
    expect(bars).toHaveLength(12);
    expect(bars[3].wet).toBe(true);
    expect(bars[0].wet).toBe(false);
    expect(bars[0].h).toBe(3);
    expect(bars[3].h).toBeGreaterThan(bars[2].h);
    // Scale floor of 5 mm: 4 mm is not a full-height bar.
    expect(bars[3].h).toBeCloseTo((4 / 5) * 70);
    expect(bars[3].y + bars[3].h).toBe(70);
  });

  it('names the wettest hour, or none when no rain is expected', () => {
    expect(heaviestHour(rain)).toBe(T('13:00'));
    expect(heaviestHour(rain.map((p) => ({ ...p, mm: 0 })))).toBeNull();
  });
});

describe('river pill', () => {
  // Sg. Binjai di Pekan Meru (JPS): alert 3.80, warning 4.00, danger 4.20 m.
  const th = { alert: 3.8, warning: 4.0, danger: 4.2 };

  it('places the JPS marks top to bottom danger, warning, alert, on the river meter scale', () => {
    const ticks = pillTicks(th);
    expect(ticks.map((k) => k.mark)).toEqual(['alert', 'warning', 'danger']);
    const [a, w, d] = ticks.map((k) => k.y);
    expect(d).toBeLessThan(w);
    expect(w).toBeLessThan(a);
    // riverScale puts alert at 3 spans of 4.75 (63.2 %) up the 104 px pill.
    expect(a).toBeCloseTo(4 + (1 - 3 / 4.75) * 104);
  });

  it('keeps the level marker inside the pill for very low and very high rivers', () => {
    expect(pillY(-5, th)).toBe(108);
    expect(pillY(9, th)).toBe(4);
  });
});

describe('scallopPath', () => {
  it('draws a closed 12-lobe badge that starts and ends at the top', () => {
    const d = scallopPath();
    expect(d.startsWith('M46.0,6.0')).toBe(true);
    expect(d.endsWith('L46.0,6.0z')).toBe(true);
    expect(d.match(/L/g)).toHaveLength(96);
  });
});

describe('ring', () => {
  it('fills the ring arc in proportion to the chance', () => {
    const C = 2 * Math.PI * 34;
    expect(ringDash(0)).toEqual({ len: 0, C });
    expect(ringDash(0.5).len).toBeCloseTo(C / 2);
    expect(ringDash(1).len).toBeCloseTo(C);
    expect(ringDash(1.4).len).toBeCloseTo(C);
  });

  it('colours the ring green under 20 %, amber under 50 %, orange above', () => {
    expect([0, 0.19, 0.2, 0.49, 0.5, 0.9].map(ringTone)).toEqual(['ok', 'ok', 'watch', 'watch', 'warn', 'warn']);
  });

  it('tints the street badge by score: 1 to 2 green, 3 amber, 4 to 5 orange', () => {
    expect(([1, 2, 3, 4, 5] as const).map(proneTone)).toEqual(['ok', 'ok', 'watch', 'warn', 'warn']);
  });
});

describe('tide', () => {
  const tide = [0.4, 0.2, 0.9, 1.3, 1.1, 0.6].map((height_m, i) => ({ time: T(`${String(8 + i).padStart(2, '0')}:00`), height_m, filled: false }));

  it('picks the next high water after the data time', () => {
    expect(nextHighWater(tide, T('09:30'))).toEqual(tide[3]);
    expect(nextHighWater(tide, T('11:30'))).toBeNull();
  });

  it('draws the wave over the hours sent, the past shaded up to now, now on the line', () => {
    const w = tideWave(tide, T('09:30'));
    expect(w.now.x).toBeCloseTo((1.5 / 5) * 210);
    // Halfway between 0.2 and 0.9 m on a 0.2 to 1.3 m scale.
    expect(w.now.y).toBeCloseTo(84 - 8 - ((0.55 - 0.2) / 1.1) * (84 - 16));
    expect(w.line.startsWith('M0.0,')).toBe(true);
    expect(w.past.endsWith(`L${w.now.x.toFixed(1)},84 L0,84z`)).toBe(true);
    expect(w.labels.map((l) => l.time)).toEqual([T('08:00'), T('10:00'), T('13:00')]);
  });
});

describe('clockHands', () => {
  it('turns the hands for the data time', () => {
    expect(clockHands(T('09:00'))).toEqual({ hour: 270, minute: 0 });
    expect(clockHands(T('18:15'))).toEqual({ hour: 187.5, minute: 90 });
  });
});
