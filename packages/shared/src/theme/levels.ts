import type { Lang, Level } from '../api/types';

/** Level colours: background + text colour with contrast >= 4.5:1. */
export const LEVEL_STYLE: Record<Level, { bg: string; fg: string; line: string }> = {
  normal: { bg: '#2e7d32', fg: '#ffffff', line: '#43a047' },
  watch: { bg: '#f9a825', fg: '#1a1a1a', line: '#fbc02d' },
  warning: { bg: '#e65100', fg: '#ffffff', line: '#ef6c00' },
  danger: { bg: '#b71c1c', fg: '#ffffff', line: '#d32f2f' },
};

export const LEVEL_LABEL: Record<Lang, Record<Level, string>> = {
  en: { normal: 'Normal', watch: 'Watch', warning: 'Warning', danger: 'Danger' },
  ms: { normal: 'Normal', watch: 'Waspada', warning: 'Amaran', danger: 'Bahaya' },
};

export const LEVEL_ORDER: Level[] = ['normal', 'watch', 'warning', 'danger'];
