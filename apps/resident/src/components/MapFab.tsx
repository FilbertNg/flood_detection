import { Link } from 'react-router';
import type { Lang } from '@floodready/shared';
import { t } from '../lib/i18n';
import { Icon } from './Icons';

/** Red floating map button on the street pages: opens the flood map with the location chooser. */
export function MapFab({ lang }: { lang: Lang }) {
  return (
    <Link to="/map" className="fab" aria-label={t(lang, 'fabLabel')}>
      <Icon name="map" />
    </Link>
  );
}
