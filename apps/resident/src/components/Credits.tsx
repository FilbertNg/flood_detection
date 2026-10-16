import type { Lang } from '@floodready/shared';
import { t } from '../lib/i18n';

/** Short visible attribution plus the full licence text, which must stay reachable on every map screen. */
export function Credits({ lang }: { lang: Lang }) {
  return (
    <div className="credits">
      <p>{t(lang, 'creditsShort')}</p>
      <details className="credits-full">
        <summary>{t(lang, 'sources')}</summary>
        <p>{t(lang, 'credits')}</p>
      </details>
    </div>
  );
}
