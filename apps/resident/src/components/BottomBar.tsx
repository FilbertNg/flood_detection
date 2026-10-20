import { Link } from 'react-router';
import { LEVEL_LABEL, type Lang, type Level } from '@floodready/shared';
import { t, tf } from '../lib/i18n';
import { Icon } from './Icons';

export interface Dot {
  id: string;
  name: string;
  level: Level;
}

/** Dot colour for a street in trouble (solid level colours on the white bar), so an alert on another page shows from any page. */
const ALERT_TINT: Partial<Record<Level, string>> = { warning: '#e65100', danger: '#c62828' };

/**
 * Bottom bar of the swipe home, like the iOS weather app: flood map on the left, one dot per saved
 * street in the middle (none for a single unsaved street), the street list on the right.
 */
export function BottomBar({ lang, dots, active = 0, onDot }: { lang: Lang; dots?: Dot[]; active?: number; onDot?: (index: number) => void }) {
  return (
    <nav className="bottom-bar" aria-label={t(lang, 'pagerLabel')}>
      <Link to="/map" className="bar-button" aria-label={t(lang, 'navMap')}>
        <Icon name="map" />
      </Link>
      <div className="bar-dots">
        {dots?.map((d, i) => {
          const tint = ALERT_TINT[d.level];
          return (
            <button
              key={d.id}
              type="button"
              className="bar-dot"
              aria-label={tf(lang, 'dotLabel', { n: i + 1, total: dots.length, name: d.name, level: LEVEL_LABEL[lang][d.level] })}
              aria-current={i === active ? 'true' : undefined}
              data-alert={tint ? d.level : undefined}
              style={tint ? { ['--dot' as string]: tint } : undefined}
              onClick={() => onDot?.(i)}
            >
              <span aria-hidden="true" />
            </button>
          );
        })}
      </div>
      <Link to="/streets" className="bar-button" aria-label={t(lang, 'navList')}>
        <Icon name="list" />
      </Link>
    </nav>
  );
}
