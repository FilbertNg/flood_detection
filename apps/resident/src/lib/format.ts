import type { Lang, RiverForecast, TimeWindow } from '@floodready/shared';
import { t } from './i18n';

/** "09:30" from "2024-11-12T09:30:00+08:00" (times are always MYT). */
export function hhmm(iso: string): string {
  return iso.slice(11, 16);
}

/** "12 Nov 2024, 09:00" */
export function dayTime(iso: string): string {
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const [y, m, d] = iso.slice(0, 10).split('-');
  return `${Number(d)} ${months[Number(m) - 1]} ${y}, ${hhmm(iso)}`;
}

/** "between 09:30 and 10:30" */
export function windowText(window: TimeWindow, lang: Lang): string {
  return `${t(lang, 'between')} ${hhmm(window.start)} ${t(lang, 'and')} ${hhmm(window.end)}`;
}

export function percent(p: number): string {
  return `${Math.round(p * 100)}%`;
}

export interface RiverForecastText {
  /** "Sg. Binjai: 3.52 m now (09:00)" */
  now: string;
  /** One line per horizon: "likely 3.90 m (3.70 to 4.10 m) by 10:00" */
  points: string[];
  /** "Warning level: 4.00 m", or null if the station has none. */
  warning: string | null;
  /** True when the upper estimate at any horizon reaches the warning level. */
  mayReachWarning: boolean;
}

/** Metres with 2 decimals and a real minus sign: "−0.80 m". */
export function metres(v: number): string {
  return `${v < 0 ? '−' : ''}${Math.abs(v).toFixed(2)} m`;
}

function range(lo: number, hi: number, lang: Lang): string {
  const strip = (v: number) => metres(v).replace(/ m$/, '');
  return `${strip(lo)} ${t(lang, 'riverTo')} ${strip(hi)} m`;
}

/** Text for the river forecast block; null when there is nothing to show. */
export function riverForecastText(rf: RiverForecast | null, lang: Lang): RiverForecastText | null {
  if (!rf || rf.points.length === 0) return null;
  const at = rf.wl_now_time ? ` (${hhmm(rf.wl_now_time)})` : '';
  return {
    now: `${rf.name}: ${metres(rf.wl_now_m)} ${t(lang, 'riverNow')}${at}`,
    points: rf.points.map(
      (p) => `${t(lang, 'riverLikely')} ${metres(p.wl_m)} (${range(p.wl_m_p10, p.wl_m_p90, lang)}) ${t(lang, 'riverBy')} ${hhmm(p.time)}`,
    ),
    warning: rf.warning_m === null ? null : `${t(lang, 'riverWarningAt')}: ${metres(rf.warning_m)}`,
    mayReachWarning: rf.warning_m !== null && rf.points.some((p) => p.wl_m_p90 >= rf.warning_m!),
  };
}
