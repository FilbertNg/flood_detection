import { useParams } from 'react-router';
import type { Lang } from '@floodready/shared';
import { StreetView } from '../components/StreetView';

/** Route wrapper: one street by its id in the URL. The swipe home renders StreetView directly. */
export function StreetPage({ lang, deviceId, onLang }: { lang: Lang; deviceId: string; onLang?: (lang: Lang) => void }) {
  const { id = '' } = useParams();
  return <StreetView id={id} lang={lang} deviceId={deviceId} onLang={onLang} />;
}
