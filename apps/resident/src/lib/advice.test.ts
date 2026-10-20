import { describe, expect, it } from 'vitest';
import { adviceSteps } from './advice';

const T = (hm: string) => `2024-11-12T${hm}:00+08:00`;
const titles = (steps: { title: string }[]) => steps.map((s) => s.title);

describe('adviceSteps', () => {
  it('Normal: nothing to do, pack a go-bag, save the numbers', () => {
    const steps = adviceSteps('normal', 2, null, 'en');
    expect(titles(steps)).toEqual(['Nothing to do right now.', 'Good time to pack a go-bag.', 'Save the emergency numbers.']);
    expect(steps[2].note).toBe('999 for emergencies, 994 for Bomba.');
  });

  it('Watch: car step names an early-flooding street only when it is flood-prone', () => {
    const prone = adviceSteps('watch', 4, null, 'en');
    expect(titles(prone)).toEqual(['Charge your phone and power bank.', 'Put your go-bag by the door.', 'Move your car if you park on this street.', 'Check on elderly neighbours.']);
    expect(prone[2].note).toBe('This street floods early (flood-prone 4 of 5).');
    expect(adviceSteps('watch', 2, null, 'en')[2].note).toBeUndefined();
  });

  it('Warning: includes the expected time in the leave step', () => {
    const steps = adviceSteps('warning', 5, { start: T('09:30'), end: T('10:30') }, 'en');
    expect(steps[0].title).toBe('Move your car to higher ground now.');
    expect(steps[2]).toEqual({ title: 'Get ready to leave.', note: 'Flooding expected between 09:30 and 10:30.' });
    expect(steps[3]).toEqual({ title: 'Do not drive through water.', note: '30 cm of moving water can float a car.' });
  });

  it('Danger: relief centre wording is generic (no invented place names)', () => {
    const steps = adviceSteps('danger', 3, null, 'ms');
    expect(steps[0].title).toBe('Naik ke tingkat atas atau pergi ke pusat pemindahan (PPS) terdekat.');
    expect(steps).toHaveLength(4);
    expect(steps[3].title).toBe('Hubungi 999 jika anda terperangkap.');
  });

  it('has 2 to 4 steps for every level in both languages', () => {
    for (const level of ['normal', 'watch', 'warning', 'danger'] as const) {
      for (const lang of ['en', 'ms'] as const) {
        const n = adviceSteps(level, 5, null, lang).length;
        expect(n).toBeGreaterThanOrEqual(2);
        expect(n).toBeLessThanOrEqual(4);
      }
    }
  });
});
