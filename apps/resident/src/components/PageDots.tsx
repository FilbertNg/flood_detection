import { LEVEL_LABEL, type Lang, type Level } from '@floodready/shared';
import { t, tf } from '../lib/i18n';

export interface Dot {
  id: string;
  name: string;
  level: Level;
}

/** Dot colour for a street in trouble (solid level colours on white), so an alert on another page shows from any page. */
const ALERT_TINT: Partial<Record<Level, string>> = { warning: '#e65100', danger: '#c62828' };

/**
 * Page dots under the hero card: one per saved street, the active one a short red pill. Each dot is a
 * button that jumps to that street. Nothing is drawn for a single street (there is nowhere to swipe).
 */
export function PageDots({ lang, dots, active, onDot }: { lang: Lang; dots: Dot[]; active: number; onDot: (index: number) => void }) {
  if (dots.length < 2) return null;
  return (
    <div className="page-dots" role="group" aria-label={t(lang, 'pagerLabel')}>
      {dots.map((d, i) => {
        const tint = ALERT_TINT[d.level];
        return (
          <button
            key={d.id}
            type="button"
            className="page-dot"
            aria-label={tf(lang, 'dotLabel', { n: i + 1, total: dots.length, name: d.name, level: LEVEL_LABEL[lang][d.level] })}
            aria-current={i === active ? 'true' : undefined}
            data-alert={tint ? d.level : undefined}
            style={tint ? { ['--dot' as string]: tint } : undefined}
            onClick={() => onDot(i)}
          >
            <span aria-hidden="true" />
          </button>
        );
      })}
    </div>
  );
}
