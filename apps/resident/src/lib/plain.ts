import type { Lang, Level, TimeWindow } from '@floodready/shared';
import { hhmm } from './format';
import { t, tf, type StringKey } from './i18n';
import type { Thresholds } from './river';
import type { GaugeRain, WeatherHour } from './weather';

/**
 * Plain-language wording for the street page. These only describe data the page already has
 * (level, window, gauge rain, river reading, Open-Meteo chance); they never change a level.
 */

const WORD: Record<Level, StringKey> = { normal: 'wordNormal', watch: 'wordWatch', warning: 'wordWarning', danger: 'wordDanger' };

/** The official level turned into one instruction word. */
export function bigWord(level: Level, lang: Lang): string {
  return t(lang, WORD[level]);
}

/** One sentence that says no more than the level and window say. */
export function headline(level: Level, window: TimeWindow | null, lang: Lang): string {
  if (level === 'normal') return t(lang, 'headNormal');
  if (level === 'watch') return t(lang, 'headWatch');
  if (level === 'warning') return window ? tf(lang, 'headWarningAt', { time: hhmm(window.start) }) : t(lang, 'headWarning');
  return t(lang, 'headDanger');
}

export type RainStrength = 'none' | 'light' | 'moderate' | 'heavy';

/** mm in the last hour → strength (WMO: light under 2.5 mm/h, heavy from 10 mm/h). */
export function rainStrength(mm: number): RainStrength {
  if (mm <= 0) return 'none';
  if (mm < 2.5) return 'light';
  if (mm < 10) return 'moderate';
  return 'heavy';
}

export type RiverStatus = 'low' | 'near' | 'alert' | 'warning' | 'danger';

/** "near" is within 0.3 m below the JPS alert mark (display wording only). */
export function riverStatus(wl: number, th: Thresholds): RiverStatus {
  if (wl >= th.danger) return 'danger';
  if (wl >= th.warning) return 'warning';
  if (wl >= th.alert) return 'alert';
  if (wl >= th.alert - 0.3) return 'near';
  return 'low';
}

/** Rain chance at which we call rain "likely", for wording only. */
const LIKELY = 40;

function chancesFrom(hours: WeatherHour[] | null, dataTime: string): { hour: string; chance: number }[] {
  if (!hours) return [];
  const start = dataTime.slice(0, 13);
  return hours
    .filter((h) => h.hour >= start && h.rainChance !== null)
    .slice(0, 12)
    .map((h) => ({ hour: h.hour, chance: h.rainChance! }));
}

const hourLabel = (hour: string) => `${hour.slice(11, 13)}:00`;

/** "easing by 20:00" when rain is likely now and drops later; "rain likely from 15:00" for the reverse. */
export function weatherPhrase(hours: WeatherHour[] | null, dataTime: string, lang: Lang): string | null {
  const c = chancesFrom(hours, dataTime);
  if (c.length < 2) return null;
  if (c[0].chance >= LIKELY) {
    const ease = c.find((h) => h.chance < LIKELY);
    return ease ? tf(lang, 'phraseEasing', { time: hourLabel(ease.hour) }) : null;
  }
  const start = c.find((h) => h.chance >= 50);
  return start ? tf(lang, 'phraseFrom', { time: hourLabel(start.hour) }) : null;
}

const STRENGTH: Record<Exclude<RainStrength, 'none'>, StringKey> = { light: 'rainLight', moderate: 'rainModerate', heavy: 'rainHeavy' };
const RIVER_SHORT: Record<RiverStatus, StringKey> = { low: 'riverLow', near: 'riverNear', alert: 'riverAlert', warning: 'riverWarning', danger: 'riverDanger' };

export interface KeyPointInput {
  lang: Lang;
  level: Level;
  window: TimeWindow | null;
  gauge: GaugeRain | null;
  hours: WeatherHour[] | null;
  dataTime: string;
  river: { wl: number; th: Thresholds } | null;
}

/** Two or three words each for the Rain / River / Flood chips. */
export function keyPoints({ lang, level, window, gauge, hours, dataTime, river }: KeyPointInput) {
  const c = chancesFrom(hours, dataTime);
  let rain: string;
  const strength = gauge ? rainStrength(gauge.mm) : 'none';
  if (strength !== 'none') {
    // Easing: the chance drops below "likely" within the next three hours.
    const easing = c.slice(1, 4).some((h) => h.chance < LIKELY);
    rain = tf(lang, easing ? 'rainEasing' : 'rainNowT', { s: t(lang, STRENGTH[strength]) });
  } else if (c[0] && c[0].chance >= LIKELY) {
    rain = t(lang, 'rainSoon');
  } else {
    rain = t(lang, 'rainNone');
  }

  const riverText = river ? t(lang, RIVER_SHORT[riverStatus(river.wl, river.th)]) : t(lang, 'riverNone');

  const flood =
    level === 'normal' ? t(lang, 'floodNo')
      : level === 'watch' ? t(lang, 'floodPossible')
        : level === 'warning' ? (window ? tf(lang, 'floodFrom', { time: hhmm(window.start) }) : t(lang, 'floodLikely'))
          : t(lang, 'floodNowLikely');

  return { rain, river: riverText, flood };
}
