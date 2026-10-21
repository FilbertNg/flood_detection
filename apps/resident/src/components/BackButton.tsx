import { Link } from 'react-router';
import type { Lang } from '@floodready/shared';
import { t } from '../lib/i18n';

/** Round back button on every screen: a red arrow on a white circle; "Back" is its name for screen readers. */
export function BackButton({ lang, to = '/' }: { lang: Lang; to?: string }) {
  return (
    <Link to={to} className="back-btn" aria-label={t(lang, 'back')}>
      <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round">
        <path d="M19 12H5.5M11.5 5.5 5 12l6.5 6.5" />
      </svg>
    </Link>
  );
}
