import type { Lang } from '@floodready/shared';
import { t } from '../lib/i18n';

/** iPhone Safari only delivers Web Push to an installed app: show the Add to Home Screen steps. */
export function InstallGuide({ lang }: { lang: Lang }) {
  return (
    <section className="install" aria-labelledby="install-title">
      <h2 id="install-title">{t(lang, 'installTitle')}</h2>
      <p className="muted">{t(lang, 'installWhy')}</p>
      <ol className="install-steps">
        <li>{t(lang, 'installStep1')}</li>
        <li>{t(lang, 'installStep2')}</li>
        <li>{t(lang, 'installStep3')}</li>
        <li>{t(lang, 'installStep4')}</li>
      </ol>
    </section>
  );
}
