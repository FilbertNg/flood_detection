import type { Lang, TimeWindow } from '@floodready/shared';
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
